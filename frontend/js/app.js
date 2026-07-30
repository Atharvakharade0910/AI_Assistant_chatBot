const $=id=>document.getElementById(id);
const e={
 list:$("conversationList"),messages:$("messages"),title:$("chatTitle"),subtitle:$("chatSubtitle"),
 input:$("messageInput"),send:$("sendButton"),stop:$("stopButton"),newChat:$("newChatButton"),
 del:$("deleteButton"),clear:$("clearAllButton"),search:$("searchInput"),rename:$("renameButton"),
 modal:$("renameModal"),renameInput:$("renameInput"),saveRename:$("saveRename"),
 cancelRename:$("cancelRename"),theme:$("themeButton"),sidebar:$("sidebar"),
 menu:$("menuButton"),close:$("closeSidebar"),toast:$("toast")
};
const state={active:null,conversations:[],controller:null,generating:false,lastUser:""};

marked.setOptions({breaks:true,gfm:true});

function toast(message){
  e.toast.textContent=message;e.toast.classList.add("show");
  setTimeout(()=>e.toast.classList.remove("show"),1800);
}
function time(value){
  return value?new Date(value).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"}):"Now";
}
async function api(url,options={}){
  const response=await fetch(url,options);
  if(!response.ok){
    let message="Request failed.";
    try{const data=await response.json();message=data.detail||message;}catch(_){}
    throw new Error(message);
  }
  return response;
}
function bottom(){e.messages.scrollTop=e.messages.scrollHeight;}
function welcome(){
  e.messages.innerHTML=`<section class="welcome">
    <div class="welcome-logo">✦</div><h2>What can I help you with?</h2>
    <p>Ask questions, request code, or continue a conversation. Responses stream live and chats are saved locally.</p>
    <div class="suggestions">
      <button class="suggestion">Explain machine learning simply</button>
      <button class="suggestion">Write a Python palindrome program</button>
      <button class="suggestion">Help me prepare for an AI interview</button>
      <button class="suggestion">Explain FastAPI with an example</button>
    </div></section>`;
  document.querySelectorAll(".suggestion").forEach(button=>button.onclick=()=>{
    e.input.value=button.textContent.trim();resize();e.input.focus();
  });
}
function message(role,content,createdAt=null){
  const row=document.createElement("article");row.className=`message-row ${role}`;
  const avatar=document.createElement("div");avatar.className="avatar";avatar.textContent=role==="user"?"YOU":"AI";
  const column=document.createElement("div");column.className="message-column";
  const body=document.createElement("div");body.className="message-content";
  role==="assistant"?body.innerHTML=marked.parse(content||""):body.textContent=content;
  column.appendChild(body);

  if(role==="assistant"){
    const actions=document.createElement("div");actions.className="message-actions";
    const copy=document.createElement("button");copy.className="message-action";copy.textContent="Copy";
    copy.onclick=async()=>{await navigator.clipboard.writeText(body.dataset.raw||content);toast("Response copied");};
    const regen=document.createElement("button");regen.className="message-action";regen.textContent="Regenerate";
    regen.onclick=regenerate;
    actions.append(copy,regen);column.appendChild(actions);
  }

  const stamp=document.createElement("div");stamp.className="timestamp";stamp.textContent=time(createdAt);
  column.appendChild(stamp);row.append(avatar,column);e.messages.appendChild(row);bottom();
  return {row,body,stamp};
}
function renderList(){
  const query=e.search.value.trim().toLowerCase();
  const items=state.conversations.filter(c=>c.title.toLowerCase().includes(query));
  e.list.innerHTML="";
  if(!items.length){e.list.innerHTML='<div class="empty-history">No matching chats.</div>';return;}
  items.forEach(c=>{
    const button=document.createElement("button");button.className="conversation-item";
    button.textContent=c.title;button.title=c.title;
    if(Number(c.id)===Number(state.active))button.classList.add("active");
    button.onclick=()=>{openConversation(c.id);e.sidebar.classList.remove("open");};
    e.list.appendChild(button);
  });
}
async function loadList(){
  state.conversations=await (await api("/api/conversations")).json();renderList();
}
async function createConversation(){
  const c=await (await api("/api/conversations",{
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({title:"New Chat"})
  })).json();
  state.active=c.id;e.title.textContent=c.title;welcome();await loadList();e.input.focus();return c.id;
}
async function openConversation(id){
  if(state.generating)return;
  state.active=Number(id);
  const c=state.conversations.find(x=>Number(x.id)===Number(id));
  e.title.textContent=c?.title||"Chat";e.messages.innerHTML="";
  const messages=await (await api(`/api/conversations/${id}/messages`)).json();
  if(!messages.length)welcome();
  else messages.forEach(m=>{message(m.role,m.content,m.created_at);if(m.role==="user")state.lastUser=m.content;});
  renderList();
}
function setGenerating(value){
  state.generating=value;e.input.disabled=value;
  e.send.classList.toggle("hidden",value);e.stop.classList.toggle("hidden",!value);
  e.subtitle.textContent=value?"Generating response...":"Streaming enabled";
}
async function send(text,regenerateFlag=false){
  if(!text.trim()||state.generating)return;
  if(!state.active)await createConversation();
  state.lastUser=text;e.messages.querySelector(".welcome")?.remove();
  if(!regenerateFlag)message("user",text);

  const assistant=message("assistant","");assistant.body.classList.add("typing");
  state.controller=new AbortController();setGenerating(true);let full="";

  try{
    const response=await api("/api/chat",{
      method:"POST",signal:state.controller.signal,headers:{"Content-Type":"application/json"},
      body:JSON.stringify({conversation_id:state.active,message:text,regenerate:regenerateFlag})
    });
    const reader=response.body.getReader(),decoder=new TextDecoder();let buffer="";
    while(true){
      const {value,done}=await reader.read();if(done)break;
      buffer+=decoder.decode(value,{stream:true});const lines=buffer.split("\n");buffer=lines.pop()||"";
      for(const line of lines){
        if(!line.trim())continue;const event=JSON.parse(line);
        if(event.type==="chunk"){
          full+=event.content;assistant.body.dataset.raw=full;assistant.body.innerHTML=marked.parse(full);
          assistant.body.querySelectorAll("pre code").forEach(block=>hljs.highlightElement(block));bottom();
        }else if(event.type==="error"){
          full=`**Error:** ${event.content}`;assistant.body.innerHTML=marked.parse(full);
        }
      }
    }
  }catch(error){
    assistant.body.innerHTML=marked.parse(error.name==="AbortError"?(full||"*Generation stopped.*"):`**Error:** ${error.message}`);
    if(error.name==="AbortError")toast("Generation stopped");
  }finally{
    assistant.body.classList.remove("typing");setGenerating(false);state.controller=null;
    e.input.disabled=false;e.input.focus();await loadList();
    const active=state.conversations.find(x=>Number(x.id)===Number(state.active));
    if(active)e.title.textContent=active.title;
  }
}
async function regenerate(){
  if(!state.lastUser||state.generating)return;
  [...e.messages.querySelectorAll(".message-row")].reverse().find(row=>row.classList.contains("assistant"))?.remove();
  await send(state.lastUser,true);
}
function resize(){e.input.style.height="auto";e.input.style.height=`${Math.min(e.input.scrollHeight,180)}px`;}
async function deleteCurrent(){
  if(!state.active||state.generating||!confirm("Delete this conversation?"))return;
  await api(`/api/conversations/${state.active}`,{method:"DELETE"});state.active=null;await loadList();
  state.conversations.length?await openConversation(state.conversations[0].id):await createConversation();toast("Conversation deleted");
}
async function clearAll(){
  if(state.generating||!confirm("Delete all saved conversations?"))return;
  await api("/api/conversations",{method:"DELETE"});state.active=null;await createConversation();toast("All history cleared");
}
async function saveRename(){
  const title=e.renameInput.value.trim();if(!title||!state.active)return;
  await api(`/api/conversations/${state.active}`,{
    method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({title})
  });
  e.modal.classList.add("hidden");e.title.textContent=title;await loadList();toast("Conversation renamed");
}
function applyTheme(theme){
  document.documentElement.dataset.theme=theme;localStorage.setItem("simplechat-theme",theme);
  e.theme.textContent=theme==="dark"?"☀":"☾";
}

e.send.onclick=async()=>{const text=e.input.value.trim();if(!text)return;e.input.value="";resize();await send(text);};
e.input.oninput=resize;
e.input.onkeydown=event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();e.send.click();}};
e.stop.onclick=()=>state.controller?.abort();
e.newChat.onclick=async()=>{if(!state.generating){await createConversation();e.sidebar.classList.remove("open");}};
e.del.onclick=deleteCurrent;e.clear.onclick=clearAll;e.search.oninput=renderList;
e.rename.onclick=()=>{if(!state.active)return;e.renameInput.value=e.title.textContent;e.modal.classList.remove("hidden");e.renameInput.focus();e.renameInput.select();};
e.cancelRename.onclick=()=>e.modal.classList.add("hidden");e.saveRename.onclick=saveRename;
e.renameInput.onkeydown=event=>{if(event.key==="Enter")saveRename();if(event.key==="Escape")e.modal.classList.add("hidden");};
e.theme.onclick=()=>applyTheme(document.documentElement.dataset.theme==="dark"?"light":"dark");
e.menu.onclick=()=>e.sidebar.classList.add("open");e.close.onclick=()=>e.sidebar.classList.remove("open");

(async()=>{
  try{
    applyTheme(localStorage.getItem("simplechat-theme")||"light");await loadList();
    state.conversations.length?await openConversation(state.conversations[0].id):await createConversation();
  }catch(error){e.messages.innerHTML=`<section class="welcome"><h2>Application error</h2><p>${error.message}</p></section>`;}
})();
