"use client";

import { useFormStatus } from "react-dom";

export function SubmitButton({ children, pendingLabel = "Working…" }) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending} aria-disabled={pending}>
      {pending ? pendingLabel : children}
    </button>
  );
}
