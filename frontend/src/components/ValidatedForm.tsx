"use client";

import { useState, type ComponentProps } from "react";

function errorsIn(form: HTMLFormElement) {
  return Array.from(form.elements).flatMap(element => {
    if (!(element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement) || element.matches(":disabled") || !element.willValidate) return [];
    const label = element.labels?.[0];
    const directText = label ? Array.from(label.childNodes).filter(n => n.nodeType === Node.TEXT_NODE).map(n => n.textContent).join(" ").trim() : "";
    const text = directText || label?.querySelector("span")?.textContent || "";
    const name = element.getAttribute("aria-label") || text?.trim() || element.name || "Thông tin";
    const validity = element.validity;
    if (validity.valueMissing || (element.required && element.type !== "checkbox" && !element.value.trim())) return [`${name}: Vui lòng ${element.type === "checkbox" ? "đánh dấu xác nhận" : "nhập hoặc chọn thông tin"}.`];
    if (validity.typeMismatch) return [`${name}: ${element.type === "email" ? "Email không đúng định dạng" : "Thông tin không đúng định dạng"}.`];
    if (validity.patternMismatch) return [`${name}: ${element.title || "Thông tin không đúng định dạng"}.`];
    if ("minLength" in element && element.minLength > 0 && element.value.length && element.value.length < element.minLength) return [`${name}: Cần ít nhất ${element.minLength} ký tự.`];
    if (validity.rangeUnderflow || validity.rangeOverflow || validity.stepMismatch || validity.badInput) return [`${name}: Vui lòng nhập số hợp lệ trong giới hạn cho phép.`];
    return [];
  });
}

/** Show all invalid fields in Vietnamese, and remove each error when corrected. */
export function ValidatedForm({ onSubmit, onInput, children, ...props }: ComponentProps<"form">) {
  const [errors, setErrors] = useState<string[]>([]);
  return <form {...props} noValidate onInput={event => { if (errors.length) setErrors(errorsIn(event.currentTarget)); onInput?.(event); }} onSubmit={event => {
    const next = errorsIn(event.currentTarget);
    setErrors(next);
    if (next.length) {
      event.preventDefault();
      const form = event.currentTarget;
      requestAnimationFrame(() => form.querySelector('[role="alert"]')?.scrollIntoView({block:"nearest"}));
      return;
    }
    onSubmit?.(event);
  }}>
    {errors.length > 0 && <ul role="alert" className="col-span-full space-y-1 rounded-xl bg-danger/5 p-3 text-sm text-danger">{errors.map(message => <li key={message}>{message}</li>)}</ul>}
    {children}
  </form>;
}
