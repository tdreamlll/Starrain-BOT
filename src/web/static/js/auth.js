import{fetchWithTimeout,sanitizeError}from'./api.js';

const TOKEN_KEY='token';

const getToken=()=>sessionStorage.getItem(TOKEN_KEY)||'';
const setToken=(t)=>sessionStorage.setItem(TOKEN_KEY,t);
const clearToken=()=>sessionStorage.removeItem(TOKEN_KEY);

const login=async(username,password,onSuccess,onError)=>{
try{
const res=await fetchWithTimeout('/api/login',{
method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({username,password})
},10000);
const data=await res.json().catch(()=>({}));
if(data.success){
setToken(data.token);
onSuccess(data.token);
}else{
onError(data.error||'登录失败');
}
}catch(e){
onError(sanitizeError(e.message));
}
};

const logout=async(token)=>{
try{
await fetchWithTimeout('/api/logout',{
method:'POST',
headers:{'Authorization':`Bearer ${token}`}
},5000);
}catch(e){}
clearToken();
};

const checkAuth=async(token)=>{
if(!token)return false;
try{
const res=await fetchWithTimeout('/api/status',{
headers:{'Authorization':`Bearer ${token}`}
});
return res.ok;
}catch(e){
return false;
}
};

export{getToken,setToken,clearToken,login,logout,checkAuth};
