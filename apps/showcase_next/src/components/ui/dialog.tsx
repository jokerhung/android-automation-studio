'use client';
import { useEffect, useRef, type ReactNode } from 'react';
export function Dialog({open,title,onClose,children}:{open:boolean;title:string;onClose():void;children:ReactNode}){const ref=useRef<HTMLDialogElement>(null);useEffect(()=>{const dialog=ref.current;if(!dialog)return;if(open&&!dialog.open)dialog.showModal();if(!open&&dialog.open)dialog.close();},[open]);return <dialog ref={ref} aria-labelledby="dialog-title" onCancel={event=>{event.preventDefault();onClose();}} onClick={event=>event.stopPropagation()}><h2 id="dialog-title">{title}</h2>{children}</dialog>}
