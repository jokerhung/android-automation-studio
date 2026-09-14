# Start with Windows

Open **Settings → Start with Windows** and enable the switch to launch the
ARTEMIS background server at the next sign-in of the current Windows user.
Installing this feature does not enable it automatically.

- Uses the current server port (for example 8009), bound to `127.0.0.1`.
- Runs via `pythonw.exe`; no terminal or browser window opens.
- Stores only an absolute launcher command in the current user's
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` value named `Artemis`.
  No administrator access or API credentials are required in the registry.
- Turning it off deletes only that registry value; it does not stop the current
  server, delete schedules or remove other startup applications.
- On supported installations, sign-in starts a persistent ARTEMIS system tray for the configured workspace and port. The menu provides **Start**, **Stop**, **Open homepage**, and **Exit**.
- Stop keeps the tray running. Exit safely stops the verified daemon and then closes the tray. Active work uses the drain/confirmation policy rather than force-kill by default.
- If the port is occupied by an unverified listener, the tray reports a port conflict and never kills or restarts it. Daemon logs remain in the usual Artemis logs folder.
- Windows may place the icon under **Show hidden icons**. If the optional tray backend is unavailable, startup falls back to the previous background-daemon behavior.
- Keep this Python installation and workspace at the registered paths. After
  moving/reinstalling Artemis or changing its port, toggle off and on to register
  the new paths/port.
- This is sign-in startup, not a Windows service: it cannot run before login,
  wake the PC or unlock Android. Windows Startup Apps/Task Manager or organization
  policy can disable a registered Run entry; the switch reports registry
  registration, not an override of those Windows policies.
- Enabled task schedules may run once the daemon starts, subject to scheduler
  misfire policy and device readiness.

The setting is local-only and unavailable on non-Windows servers. After updating
the backend code, restart Artemis once before using the switch. Frontend changes
also require the normal Web UI build and page refresh.

Verification uses mocked registry and process operations; a real sign-out/reboot
is not performed automatically during development.
