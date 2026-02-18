let ws=null;
let wsConnected=false;
let onMessageCallback=null;
let onStatusChange=null;

const sha256=async(message)=>{
const msgBuffer=new TextEncoder().encode(message);
const hashBuffer=await crypto.subtle.digest('SHA-256',msgBuffer);
const hashArray=Array.from(new Uint8Array(hashBuffer));
return hashArray.map(b=>b.toString(16).padStart(2,'0')).join('');
};

const getNonce=async(token)=>{
try{
const res=await fetch('/api/ws/nonce',{
headers:{'Authorization':`Bearer ${token}`}
});
if(!res.ok)return null;
const data=await res.json();
return data.nonce;
}catch(e){
return null;
}
};

const connectWS=async(token,onMsg,onStatus)=>{
if(ws){ws.close();}
onMessageCallback=onMsg;
onStatusChange=onStatus;

const nonce=await getNonce(token);
if(!nonce){
if(onStatusChange)onStatusChange(null,'nonce_failed');
return;
}

const signature=await sha256(`${nonce}:${token}`);

const protocol=location.protocol==='https:'?'wss:':'ws:';
ws=new WebSocket(`${protocol}//${location.host}/ws`);
ws.onopen=()=>{
ws.send(JSON.stringify({nonce,signature}));
};
ws.onclose=(e)=>{
wsConnected=false;
if(onStatusChange)onStatusChange(false);
if(e.code===4001){
if(onStatusChange)onStatusChange(null,'expired');
return;
}
if(e.code===4003){
if(onStatusChange)onStatusChange(null,'max_conn');
return;
}
setTimeout(()=>{if(token)connectWS(token,onMsg,onStatus);},3000);
};
ws.onerror=()=>{};
ws.onmessage=(e)=>{
try{
const data=JSON.parse(e.data);
if(data.type==='auth'&&data.status==='ok'){
wsConnected=true;
if(onStatusChange)onStatusChange(true);
return;
}
if(onMessageCallback)onMessageCallback(data);
}catch(err){}
};
};

const disconnectWS=()=>{
if(ws){ws.close();ws=null;}
wsConnected=false;
};

const sendWS=(data)=>{
if(ws&&ws.readyState===WebSocket.OPEN){
ws.send(JSON.stringify(data));
}
};

export{connectWS,disconnectWS,sendWS,wsConnected};
