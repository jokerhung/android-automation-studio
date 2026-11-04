from __future__ import annotations
import json
import ssl
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from admin_console.routers import email_settings as email_router
from admin_console.schemas.email_schema import EmailSettingsResponse, EmailSettingsUpdate, SendTestEmailRequest
from admin_console.services.email_settings_service import EmailSettingsConflict, EmailSettingsError, EmailSettingsService
from admin_console.services.secret_store import SecretStore, SecretStoreUnsupported, create_secret_store
from admin_console.services.smtp_service import SMTPService

class MemorySecretStore(SecretStore):
 def __init__(self):self.values={}
 def protect(self,value):return value.encode().hex().encode()
 def unprotect(self,value):return bytes.fromhex(value.decode()).decode()
 def get(self,key):return self.values.get(key)
 def set(self,key,value):self.values[key]=value
 def delete(self,key):return self.values.pop(key,None) is not None

def payload(**overrides):
 value={"smtp_host":"smtp.example.com","smtp_port":587,"security":"starttls","smtp_username":"user@example.com","password":"honey-secret","sender_email":"sender@example.com","sender_name":"Artemis","enabled":True,"expected_version":0};value.update(overrides);return EmailSettingsUpdate(**value)

def test_schema_rejects_urls_bad_mailboxes_and_header_injection():
 for change in ({"smtp_host":"https://smtp.example.com"},{"sender_email":"Display <sender@example.com>"},{"sender_name":"Artemis\r\nBcc: victim@example.com"}):
  with pytest.raises(ValidationError):payload(**change)
 with pytest.raises(ValidationError):SendTestEmailRequest(recipient_email="x@example.com\nBcc:y@example.com",subject="ok")
 with pytest.raises(ValidationError):SendTestEmailRequest(recipient_email="x@example.com",subject="ok\r\nBcc:y@example.com")

def test_password_is_write_only_and_blank_preserves_secret(tmp_path):
 store=MemorySecretStore();service=EmailSettingsService(store,tmp_path/"email.json");result=service.update(payload())
 assert result.password_configured is True and "password" not in result.model_dump()
 assert not (tmp_path/"email.json").exists()
 assert "honey-secret" not in service.store.path.read_bytes().decode("latin-1")
 second=service.update(payload(password="",expected_version=1,sender_name="Updated"))
 assert second.version==2 and service.connection_parameters()[1]=="honey-secret"

def test_version_conflict_and_clear_disables_email(tmp_path):
 store=MemorySecretStore();service=EmailSettingsService(store,tmp_path/"email.json");service.update(payload())
 with pytest.raises(EmailSettingsConflict):service.update(payload(expected_version=0))
 cleared=service.clear_password();assert cleared.password_configured is False and cleared.enabled is False and cleared.version==2

def test_non_windows_store_is_explicitly_unsupported(monkeypatch):
 import admin_console.services.secret_store as module
 monkeypatch.setattr(module.sys,"platform","linux")
 with pytest.raises(SecretStoreUnsupported):create_secret_store()

def verified_context():
 context=ssl.create_default_context();assert context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname;return context

def test_starttls_and_ssl_use_verified_tls_without_network():
 plain=MagicMock();ssl_client=MagicMock();plain_factory=MagicMock(return_value=plain);ssl_factory=MagicMock(return_value=ssl_client)
 service=SMTPService(smtp_factory=plain_factory,smtp_ssl_factory=ssl_factory,ssl_context_factory=verified_context)
 settings=EmailSettingsResponse(smtp_host="smtp.example.com",smtp_port=587,security="starttls",smtp_username="user",sender_email="sender@example.com",password_configured=True)
 service.test_connection(settings,"secret");plain.starttls.assert_called_once();plain.login.assert_called_once_with("user","secret");ssl_factory.assert_not_called()
 settings=settings.model_copy(update={"security":"ssl","smtp_port":465});service.test_connection(settings,"secret");ssl_factory.assert_called_once();ssl_client.login.assert_called_once()

def app_with(service,smtp):
 app=FastAPI();app.include_router(email_router.router);app.dependency_overrides[email_router.get_email_settings_service]=lambda:service;app.dependency_overrides[email_router.get_smtp_service]=lambda:smtp;return app

@pytest.mark.asyncio
async def test_api_never_returns_password_and_mocks_all_smtp(tmp_path):
 store=MemorySecretStore();service=EmailSettingsService(store,tmp_path/"email.json");smtp=MagicMock();app=app_with(service,smtp)
 async with AsyncClient(transport=ASGITransport(app=app),base_url="http://localhost") as client:
  response=await client.put("/api/settings/email",json=payload().model_dump(mode="json"),headers={"Origin":"http://localhost"})
  assert response.status_code==200 and response.json()["password_configured"] is True and "honey-secret" not in response.text and "password" not in response.json()
  assert (await client.get("/api/settings/email")).json()["password_configured"] is True
  assert (await client.post("/api/settings/email/test-connection")).status_code==200
  assert (await client.post("/api/settings/email/send-test",json={"recipient_email":"recipient@example.com","subject":"Safe test"})).status_code==200
 smtp.test_connection.assert_called_once();smtp.send_test.assert_called_once()

@pytest.mark.asyncio
async def test_api_is_loopback_and_same_origin_only(tmp_path):
 app=app_with(EmailSettingsService(MemorySecretStore(),tmp_path/"email.json"),MagicMock())
 async with AsyncClient(transport=ASGITransport(app=app,client=("203.0.113.4",5000)),base_url="http://localhost") as client:
  assert (await client.get("/api/settings/email")).status_code==403
 async with AsyncClient(transport=ASGITransport(app=app),base_url="http://localhost") as client:
  assert (await client.get("/api/settings/email",headers={"Origin":"https://evil.example"})).status_code==403


@pytest.mark.asyncio
@pytest.mark.parametrize("bound_host", ["0.0.0.0", "10.201.21.211", "::"])
async def test_lan_console_can_manage_email_on_network_bound_server(tmp_path, monkeypatch, bound_host):
 from admin_console.routers.system import state
 monkeypatch.setattr(state,"host",bound_host)
 service=EmailSettingsService(MemorySecretStore(),tmp_path/"email.json")
 service.update(payload())
 smtp=MagicMock()
 app=app_with(service,smtp)
 transport=ASGITransport(app=app,client=("192.168.1.20",5000))
 async with AsyncClient(transport=transport,base_url="http://10.201.21.211:8009",headers={"Origin":"http://10.201.21.211:8009"}) as client:
  response=await client.get("/api/settings/email")
  assert response.status_code==200
  assert response.json()["smtp_host"]=="smtp.example.com"
  assert response.json()["password_configured"] is True
  assert "honey-secret" not in response.text and "password" not in response.json()
  data=payload(expected_version=1,password="",sender_name="LAN updated").model_dump(mode="json",exclude={"password"})
  response=await client.put("/api/settings/email",json=data)
  assert response.status_code==200 and response.json()["sender_name"]=="LAN updated"
  assert service.connection_parameters()[1]=="honey-secret"
  assert (await client.post("/api/settings/email/test-connection")).status_code==200
  assert (await client.post("/api/settings/email/send-test",json={"recipient_email":"test@example.com"})).status_code==200
  # A browser on a different origin is still rejected for reads and mutations.
  for method,path in [("GET",""),("PUT",""),("POST","/test-connection"),("POST","/send-test"),("DELETE","/password")]:
   response=await client.request(method,"/api/settings/email"+path,headers={"Origin":"http://other.example"})
   assert response.status_code==403
  response=await client.delete("/api/settings/email/password")
  assert response.status_code==200 and response.json()["password_configured"] is False
 smtp.test_connection.assert_called_once()
 smtp.send_test.assert_called_once()


@pytest.mark.asyncio
async def test_lan_readiness_exposes_only_boolean_and_tracks_configuration(tmp_path):
 service=EmailSettingsService(MemorySecretStore(),tmp_path/"email.json")
 app=app_with(service,MagicMock())
 async with AsyncClient(transport=ASGITransport(app=app,client=("192.168.1.20",5000)),base_url="http://192.168.1.10:8009") as client:
  response=await client.get("/api/settings/email/readiness")
  assert response.status_code==200 and response.json()=={"ready":False}
  service.update(payload())
  response=await client.get("/api/settings/email/readiness")
  assert response.status_code==200 and response.json()=={"ready":True}
  assert (await client.get("/api/settings/email")).status_code==403
  assert (await client.put("/api/settings/email",json={})).status_code==403
  service.clear_password()
  assert (await client.get("/api/settings/email/readiness")).json()=={"ready":False}


@pytest.mark.asyncio
async def test_readiness_does_not_report_storage_failure_as_unconfigured():
 service=MagicMock();service.get.side_effect=EmailSettingsError("private storage detail")
 app=app_with(service,MagicMock())
 async with AsyncClient(transport=ASGITransport(app=app,client=("192.168.1.20",5000)),base_url="http://192.168.1.10:8009") as client:
  response=await client.get("/api/settings/email/readiness")
  assert response.status_code==503
  assert response.json()=={"detail":"Unable to check SMTP readiness."}


def test_email_migrates_once_and_uses_database_after_legacy_files_change(tmp_path):
 store=MemorySecretStore();store.set("smtp-password","legacy-secret")
 path=tmp_path/"email.json"
 metadata=payload().model_dump(exclude={"password","expected_version"});metadata["version"]=3
 path.write_text(json.dumps(metadata),encoding="utf-8")
 service=EmailSettingsService(store,path)
 assert service.get().version==3
 service.update(payload(password="database-secret",expected_version=3,smtp_host="new.example.com"))
 path.unlink();store.delete("smtp-password")
 reopened=EmailSettingsService(store,path)
 settings,password=reopened.connection_parameters()
 assert settings.smtp_host=="new.example.com" and password=="database-secret"
 assert reopened.get().version==4


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_textboxes_preserve_saved_email_settings(tmp_path, blank):
    service = EmailSettingsService(MemorySecretStore(), tmp_path / "email.json")
    original = service.update(payload())
    updated = service.update(payload(
        expected_version=1, smtp_host=blank, sender_email=blank,
        sender_name=blank, smtp_username=blank, password=blank, enabled=False,
    ))
    for field in ("smtp_host", "sender_email", "sender_name", "smtp_username"):
        assert getattr(updated, field) == getattr(original, field)
    assert updated.enabled is False
    assert service.connection_parameters()[1] == "honey-secret"
