// Only for synthetic credentials from the isolated community QA database.
import { createHmac } from "node:crypto";

export function qaTotp(secret: string) {
  let bits = "";
  for (const char of secret) bits += "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567".indexOf(char).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g)!.map(byte => parseInt(byte, 2)));
  const counter = Buffer.alloc(8); counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const hash = createHmac("sha1", key).update(counter).digest();
  const value = hash.readUInt32BE(hash[19] & 15) & 0x7fffffff;
  return String(value % 1000000).padStart(6, "0");
}
