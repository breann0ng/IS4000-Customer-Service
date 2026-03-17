import { client } from "./generated/client.gen";

client.setConfig({ baseUrl: "" });

client.interceptors.request.use((request) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    request.headers.set("Authorization", `Bearer ${token}`);
  }
  return request;
});

client.interceptors.response.use((response) => {
  if (response.status === 401) {
    localStorage.removeItem("access_token");
    window.location.href = "/login";
  }
  return response;
});

export { client };
