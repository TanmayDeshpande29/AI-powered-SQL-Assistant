import { jwtDecode } from "jwt-decode";

export function GetUserId()
{
const token = localStorage.getItem("access_token");
if(!token) return null;

const decoded = jwtDecode(token);
return decoded.user_id;
}