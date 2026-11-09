export function contactPhoneError(value: string): string {
  const phone = value.trim();
  const digits = phone.replace(/^\+/, "");
  if (!/^\+?[0-9]{9,15}$/.test(phone) || new Set(digits).size < 2) {
    return "Số điện thoại không hợp lệ. Vui lòng nhập số liên lạc thật.";
  }
  return "";
}
