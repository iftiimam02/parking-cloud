const API = ""; 
// keep empty because website + API are same origin in Azure Container Apps
// if you ever separate frontend, set API = "https://your-api-url"

const TZ = "Asia/Dhaka";

function $(id){ return document.getElementById(id); }

function saveToken(t){ localStorage.setItem("token", t); }
function getToken(){ return localStorage.getItem("token"); }
function clearToken(){ localStorage.removeItem("token"); }

function fmtDhaka(isoString){
  if(!isoString) return "";
  const d = new Date(isoString);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false
  }).format(d);
}

// datetime-local gives local time (Dhaka on your PC). Convert to UTC ISO string:
function localToUtcIso(localValue){
  // localValue like "2026-03-04T22:30"
  const d = new Date(localValue);
  return d.toISOString(); // UTC ISO
}

// Convert UTC ISO to datetime-local string for display in input (optional)
function utcIsoToLocalInput(iso){
  const d = new Date(iso);
  const pad = n => String(n).padStart(2,"0");
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function apiFetch(path, opts = {}){
  const headers = opts.headers || {};
  headers["Content-Type"] = "application/json";

  const token = getToken();
  if(token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(API + path, { ...opts, headers });
  let data = null;
  try { data = await res.json(); } catch(e) {}

  if(!res.ok){
    const msg = (data && data.detail) ? data.detail : `Error ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

/* ---------------- Auth ---------------- */
async function login(username, password){
  const data = await apiFetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
  saveToken(data.access_token);
}

async function register(username, password){
  const data = await apiFetch("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
  saveToken(data.access_token);
}

/* ---------------- Slots ---------------- */
async function loadSlots(){
  return await apiFetch("/api/slots");
}

/* ---------------- Bookings ---------------- */
async function createBooking(slot_id, start_local, end_local){
  const start_time = localToUtcIso(start_local);
  const end_time = localToUtcIso(end_local);

  return await apiFetch("/api/bookings", {
    method: "POST",
    body: JSON.stringify({ slot_id, start_time, end_time })
  });
}

async function myBookings(){
  return await apiFetch("/api/bookings/me");
}

/* ---------------- Admin ---------------- */
async function adminListPending(adminUser, adminPass){
  const res = await fetch(API + "/api/admin/bookings?status=PENDING", {
    headers: {
      "X-ADMIN-USER": adminUser,
      "X-ADMIN-PASS": adminPass
    }
  });
  const data = await res.json();
  if(!res.ok) throw new Error(data.detail || "Admin error");
  return data;
}

async function adminApprove(id, adminUser, adminPass){
  const res = await fetch(API + `/api/admin/bookings/${id}/approve`, {
    method: "POST",
    headers: {
      "X-ADMIN-USER": adminUser,
      "X-ADMIN-PASS": adminPass
    }
  });
  const data = await res.json();
  if(!res.ok) throw new Error(data.detail || "Approve failed");
  return data;
}

async function adminReject(id, adminUser, adminPass){
  const res = await fetch(API + `/api/admin/bookings/${id}/reject`, {
    method: "POST",
    headers: {
      "X-ADMIN-USER": adminUser,
      "X-ADMIN-PASS": adminPass
    }
  });
  const data = await res.json();
  if(!res.ok) throw new Error(data.detail || "Reject failed");
  return data;
}