const PHONE_RE = /^\d{10}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function validateName(v: string): string | null {
  const trimmed = v.trim();
  if (!trimmed) return "Name is required.";
  if (trimmed.length < 2) return "Name must be at least 2 characters.";
  return null;
}

export function validateContact(v: string): string | null {
  const trimmed = v.trim();
  if (!trimmed) return "Phone or email is required.";
  if (!PHONE_RE.test(trimmed) && !EMAIL_RE.test(trimmed))
    return "Enter a valid 10-digit mobile number or email address.";
  return null;
}

export function validatePlayers(v: number, max: number): string | null {
  if (!Number.isInteger(v) || v < 1) return "At least 1 player required.";
  if (v > max) return `Maximum ${max} players for this slot.`;
  return null;
}

export function validateCompany(v: string): string | null {
  if (!v.trim()) return "Company name is required.";
  return null;
}

export function validateGroupSize(v: number): string | null {
  if (!Number.isInteger(v) || v < 1) return "Group size must be at least 1.";
  return null;
}
