const API_TIMEOUT=15000;

const fetchWithTimeout=async(url,options={},timeout=API_TIMEOUT)=>{
const controller=new AbortController();
const timeoutId=setTimeout(()=>controller.abort(),timeout);
try{
const res=await fetch(url,{...options,signal:controller.signal});
clearTimeout(timeoutId);
return res;
}catch(e){
clearTimeout(timeoutId);
if(e.name==='AbortError')throw new Error('请求超时');
throw e;
}
};

const sanitizeError=(error)=>{
const safeErrors={
'请求超时':'请求超时，请稍后重试',
'未授权':'会话已过期，请重新登录',
'请求过于频繁':'请求过于频繁，请稍后重试',
'网络错误':'网络连接失败',
};
return safeErrors[error]||'操作失败，请稍后重试';
};

const api=async(url,options={},tokenValue)=>{
const headers={'Content-Type':'application/json'};
if(tokenValue)headers['Authorization']=`Bearer ${tokenValue}`;
try{
const res=await fetchWithTimeout(url,{...options,headers});
const data=await res.json().catch(()=>({}));
if(res.status===401){
sessionStorage.removeItem('token');
throw new Error('未授权');
}
if(res.status===429){
throw new Error('请求过于频繁');
}
if(!res.ok){
throw new Error(data.error||'请求失败');
}
return data;
}catch(e){
if(e.message==='请求超时')throw new Error('请求超时');
if(e.name==='TypeError')throw new Error('网络错误');
throw e;
}
};

export{fetchWithTimeout,sanitizeError,api,API_TIMEOUT};
