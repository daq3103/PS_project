"use client";
import { createContext } from "react";
import type { UserDto } from "@/lib/api-client";
export const AdminUserContext = createContext<UserDto | null>(null);
