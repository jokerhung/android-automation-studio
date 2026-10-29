import type { InputHTMLAttributes, ReactNode } from 'react';
export function Field({label,hint,error,...props}:InputHTMLAttributes<HTMLInputElement>&{label:string;hint?:string;error?:string}){const id=props.id??props.name;return <label className="field" htmlFor={id}><span>{label}</span><input {...props} id={id}/>{hint&&<small>{hint}</small>}{error&&<small role="alert" className="fieldError">{error}</small>}</label>}
export function Card({children}:{children:ReactNode}){return <section className="card">{children}</section>}
