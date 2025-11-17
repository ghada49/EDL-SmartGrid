import client from "./client";

export async function startTraining(mode: string) {
  const response = await client.post(`/ops/train?mode=${mode}`);
  return response.data; // <-- THIS FIXES THE UNDEFINED BUG
}

export async function getTrainingStatus(jobId: string) {
  const response = await client.get(`/ops/train/${jobId}`);
  return response.data;
}
