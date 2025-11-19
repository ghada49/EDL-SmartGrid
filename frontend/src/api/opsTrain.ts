import client from "./client";

export async function startTraining(mode: string) {
  const response = await client.post(`/ops/train?mode=${mode}`);
  return response.data; // <-- THIS FIXES THE UNDEFINED BUG
}

export async function getTrainingStatus(jobId: string) {
  const response = await client.get(`/ops/train/${jobId}`);
  return response.data;
}

// NEW: current model card
export async function getCurrentModelCard() {
  const response = await client.get("/ops/train/model/current");
  return response.data;
}

// NEW: model history
export async function getModelHistory() {
  const response = await client.get("/ops/train/model/history");
  return response.data;
}

export async function activateModelVersion(version: number) {
  const response = await client.post("/ops/train/model/activate", { version });
  return response.data;
}
