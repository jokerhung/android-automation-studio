/** Runtime navigation with no-reload locale switching. */
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { TranslatePipe } from '../../core/i18n/translate.pipe';
@Component({
 selector:'app-nav-switcher', standalone:true, imports:[RouterLink,RouterLinkActive,TranslatePipe],
 template:`
 <nav class="floating-nav-switcher" [attr.aria-label]="'nav.main' | translate">
  <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{exact:true}" class="nav-tab-btn" [title]="'nav.homeTitle' | translate" [attr.aria-label]="'nav.home' | translate"><span class="material-symbols-outlined tab-icon">add_task</span><span class="tab-label">{{ 'nav.home' | translate }}</span></a>
  <a routerLink="/workspace" routerLinkActive="active" class="nav-tab-btn" [title]="'nav.openWorkspace' | translate" [attr.aria-label]="'nav.openWorkspace' | translate"><span class="material-symbols-outlined tab-icon">space_dashboard</span><span class="tab-label">{{ 'nav.workspace' | translate }}</span></a>
  <a routerLink="/task-schedule" routerLinkActive="active" class="nav-tab-btn" [title]="'nav.openSchedule' | translate" [attr.aria-label]="'nav.openSchedule' | translate"><span class="material-symbols-outlined tab-icon" aria-hidden="true">calendar_clock</span><span class="tab-label">{{ 'nav.schedule' | translate }}</span></a>
  <a routerLink="/settings" routerLinkActive="active" class="nav-tab-btn" [title]="'nav.openSettings' | translate" [attr.aria-label]="'nav.openSettings' | translate"><span class="material-symbols-outlined tab-icon" aria-hidden="true">settings</span><span class="tab-label">{{ 'nav.settings' | translate }}</span></a>
 </nav>`, changeDetection:ChangeDetectionStrategy.Eager, styleUrls:['./nav-switcher.component.scss']
}) export class NavSwitcherComponent {}
