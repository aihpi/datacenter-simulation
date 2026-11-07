import type { GpuType } from "../types";

export const GPU_IDLE: Record<GpuType, number> = {
  l40s: 50,
  a100: 75,
  h100: 100,
  h200: 100,
  b200: 150,
};

export const GPU_TDP: Record<GpuType, number> = {
  l40s: 350,
  a100: 400,
  h100: 700,
  h200: 700,
  b200: 1000,
};
