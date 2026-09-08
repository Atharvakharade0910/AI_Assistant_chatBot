const $=id=>document.getElementById(id);
const e={
 list:$("conversationList"),messages:$("messages"),title:$("chatTitle"),subtitle:$("chatSubtitle"),
 input:$("messageInput"),send:$("sendButton"),stop:$("stopButton"),newChat:$("newChatButton"),
 del:$("deleteButton"),clear:$("clearAllButton"),search:$("searchInput"),rename:$("renameButton"),
 modal:$("renameModal"),renameInput:$("renameInput"),saveRename:$("saveRename"),
 cancelRename:$("cancelRename"),theme:$("themeButton"),sidebar:$("sidebar"),
 menu:$("menuButton"),close:$("closeSidebar"),toast:$("toast"),auth:$("authScreen"),authForm:$("authForm"),
 authEmail:$("authEmail"),authPassword:$("authPassword"),authSubmit:$("authSubmit"),authSwitch:$("authSwitch"),
 authError:$("authError"),accountEmail:$("accountEmail"),logout:$("logoutButton")
 ,documentInput:$("documentInput"),voice:$("voiceButton"),speak:$("speakButton"),orb:$("assistantOrb"),assistantState:$("assistantState"),toolText:$("toolText"),toolStrip:$("toolStrip")
};
const state={active:null,conversations:[],controller:null,generating:false,lastUser:"",authMode:"login"};

marked.setOptions({breaks:true,gfm:true,html:false});

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
function showAuth(message=""){
  document.documentElement.dataset.theme="dark";
  e.auth.hidden=false;e.authError.textContent=message;e.authEmail.focus();document.querySelector('.app').style.display='none';
}
function showApp(user){
  applyTheme(localStorage.getItem("simplechat-theme-v2")||"dark");
  e.auth.hidden=true;document.querySelector('.app').style.display='';e.accountEmail.textContent=user.email;
}
function setAssistantState(label,mode='ready'){
  e.assistantState.textContent=label;e.assistantState.dataset.state=mode;e.orb.dataset.state=mode;e.toolText.textContent=label;e.toolStrip.dataset.state=mode;
}
async function authenticate(){
  try{const user=await (await api('/api/auth/me')).json();showApp(user);return true;}
  catch(_){showAuth();return false;}
}
function bottom(){e.messages.scrollTop=e.messages.scrollHeight;}
function welcome(){
  e.messages.innerHTML=`<section class="welcome">
    <div class="welcome-logo">✦</div><p class="welcome-kicker">ASSISTANT ONLINE</p><h2>Start with a clear question.</h2>
    <p>Your private workspace can explain ideas, write code, search current information, calculate answers, and use your uploaded documents.</p>
    <div class="suggestions">
      <button class="suggestion" data-prompt="Explain machine learning simply"><span class="suggestion-icon">01</span><strong>Learn something</strong><span>Break down a difficult topic with a simple example.</span></button>
      <button class="suggestion" data-prompt="Write a Python palindrome program"><span class="suggestion-icon">02</span><strong>Build with code</strong><span>Generate a practical solution and explain how it works.</span></button>
      <button class="suggestion" data-prompt="Help me prepare for an AI interview"><span class="suggestion-icon">03</span><strong>Prepare for an interview</strong><span>Practice questions, answers, and focused feedback.</span></button>
      <button class="suggestion" data-prompt="Explain FastAPI with an example"><span class="suggestion-icon">04</span><strong>Explore FastAPI</strong><span>Get a concise guide with a working example.</span></button>
    </div></section>`;
  document.querySelectorAll(".suggestion").forEach(button=>button.onclick=()=>{
    e.input.value=button.dataset.prompt;resize();e.input.focus();
  });
}
function message(role,content,createdAt=null,status="complete",messageId=null){
  const row=document.createElement("article");row.className=`message-row ${role}`;
  const avatar=document.createElement("div");avatar.className=`avatar ${role==="assistant"?"assistant-face":"user-face"}`;
  if(role==="assistant") avatar.innerHTML='<span class="face-eye face-eye-left"></span><span class="face-eye face-eye-right"></span><span class="face-mouth"></span>';
  else avatar.textContent="YOU";
  const column=document.createElement("div");column.className="message-column";
  const body=document.createElement("div");body.className="message-content";
  role==="assistant"?body.innerHTML=marked.parse(content||""):body.textContent=content;
  if(role==="assistant"&&!content) body.innerHTML='<span class="typing-dots" aria-label="Assistant is typing"><i></i><i></i><i></i></span>';
  if(messageId!==null)row.dataset.messageId=messageId;
  if(status!=="complete") row.dataset.status=status;
  column.appendChild(body);

  if(role==="assistant"){
    const actions=document.createElement("div");actions.className="message-actions";
    const copy=document.createElement("button");copy.className="message-action";copy.textContent="Copy";
    copy.onclick=async()=>{await navigator.clipboard.writeText(body.dataset.raw||content);toast("Response copied");};
    const regen=document.createElement("button");regen.className="message-action";regen.textContent="Regenerate";
    regen.onclick=()=>regenerate(messageId);
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
  state.lastUser="";
  const c=state.conversations.find(x=>Number(x.id)===Number(id));
  e.title.textContent=c?.title||"Chat";e.messages.innerHTML="";
  const messages=await (await api(`/api/conversations/${id}/messages`)).json();
  if(!messages.length)welcome();
  else messages.forEach(m=>{message(m.role,m.content,m.created_at,m.status,m.id);if(m.role==="user")state.lastUser=m.content;});
  renderList();
}
function setGenerating(value){
  state.generating=value;e.input.disabled=value;
  e.send.classList.toggle("hidden",value);e.stop.classList.toggle("hidden",!value);
  e.subtitle.textContent=value?"Working with your workspace":"Streaming enabled";
  if(value)setAssistantState("Thinking","thinking");else setAssistantState("Ready","ready");
}
async function send(text,regenerateFlag=false,regenerateMessageId=null){
  if(!text.trim()||state.generating)return;
  if(!state.active)await createConversation();
  state.lastUser=text;e.messages.querySelector(".welcome")?.remove();
  const lower=text.toLowerCase();
  if(/search|latest|news|current/.test(lower))setAssistantState("Searching the web","searching");
  else if(/calculate|what is \d|math/.test(lower))setAssistantState("Calculating","tool");
  else setAssistantState("Reading context","reading");
  if(!regenerateFlag)message("user",text);

  const assistant=message("assistant","");assistant.body.classList.add("typing");assistant.row.classList.add("thinking");
  state.controller=new AbortController();setGenerating(true);let full="";

  try{
    const response=await api("/api/chat",{
      method:"POST",signal:state.controller.signal,headers:{"Content-Type":"application/json"},
      body:JSON.stringify({conversation_id:state.active,message:text,regenerate:regenerateFlag,regenerate_message_id:regenerateMessageId})
    });
    const reader=response.body.getReader(),decoder=new TextDecoder();let buffer="";
    while(true){
      const {value,done}=await reader.read();if(done)break;
      buffer+=decoder.decode(value,{stream:true});const lines=buffer.split("\n");buffer=lines.pop()||"";
      for(const line of lines){
        if(!line.trim())continue;const event=JSON.parse(line);
        if(event.type==="chunk"){
          full+=event.content;assistant.row.classList.remove("thinking");assistant.row.classList.add("speaking");assistant.body.dataset.raw=full;assistant.body.innerHTML=marked.parse(full);
          assistant.body.querySelectorAll("pre code").forEach(block=>hljs.highlightElement(block));bottom();
        }else if(event.type==="done"){
          assistant.row.classList.remove("thinking","speaking");assistant.row.classList.add(event.status||"complete");
          assistant.row.dataset.status=event.status||"complete";
          setAssistantState(event.status==="cancelled"?"Paused":"Complete",event.status==="cancelled"?"paused":"complete");
        }else if(event.type==="error"){
          assistant.row.classList.remove("thinking","speaking");assistant.row.classList.add("failed");
          full=`**Error:** ${event.content}`;assistant.body.innerHTML=marked.parse(full);
          assistant.row.dataset.status="failed";
          toast("Response generation failed");
        }
      }
    }
  }catch(error){
    assistant.body.innerHTML=marked.parse(error.name==="AbortError"?(full||"*Generation stopped.*"):`**Error:** ${error.message}`);
    if(error.name==="AbortError")toast("Generation stopped");
  }finally{
    assistant.body.classList.remove("typing");setGenerating(false);state.controller=null;
    e.input.disabled=false;e.input.focus();await loadList();
    setTimeout(()=>{if(!state.generating)setAssistantState("Ready","ready");},1200);
    const active=state.conversations.find(x=>Number(x.id)===Number(state.active));
    if(active)e.title.textContent=active.title;
  }
}
async function regenerate(messageId=null){
  if(!state.lastUser||state.generating)return;
  const row=messageId===null
    ? [...e.messages.querySelectorAll(".message-row")].reverse().find(row=>row.classList.contains("assistant"))
    : e.messages.querySelector(`[data-message-id="${messageId}"]`);
  const userRow=row?.previousElementSibling?.classList.contains("user")
    ? row.previousElementSibling
    : [...e.messages.querySelectorAll(".message-row.user")].reverse()[0];
  const text=userRow?.querySelector(".message-content")?.textContent||state.lastUser;
  row?.remove();
  await send(text,true,messageId);
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
  document.documentElement.dataset.theme=theme;localStorage.setItem("simplechat-theme-v2",theme);
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
e.authSwitch.onclick=()=>{state.authMode=state.authMode==='login'?'register':'login';e.authSwitch.textContent=state.authMode==='login'?'Create an account':'Already have an account? Sign in';e.authSubmit.textContent=state.authMode==='login'?'Sign in':'Create account';e.authPassword.autocomplete=state.authMode==='login'?'current-password':'new-password';};
e.authForm.onsubmit=async event=>{event.preventDefault();e.authError.textContent='';e.authSubmit.disabled=true;try{const user=await (await api(`/api/auth/${state.authMode}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e.authEmail.value,password:e.authPassword.value})})).json();showApp(user);await loadList();state.conversations.length?await openConversation(state.conversations[0].id):await createConversation();}catch(error){e.authError.textContent=error.message;}finally{e.authSubmit.disabled=false;}};
e.logout.onclick=async()=>{if(state.generating)return;await api('/api/auth/logout',{method:'POST'});state.active=null;state.conversations=[];e.messages.innerHTML='';showAuth();};
e.documentInput.onchange=async()=>{const file=e.documentInput.files[0];if(!file)return;const form=new FormData();form.append('file',file);try{await api('/api/documents',{method:'POST',body:form});toast('Private document added');}catch(error){toast(error.message);}finally{e.documentInput.value='';}};
const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
if(SpeechRecognition){const recognition=new SpeechRecognition();recognition.lang='en-US';recognition.interimResults=false;recognition.onresult=event=>{e.input.value=event.results[0][0].transcript;resize();e.input.focus();};recognition.onerror=()=>toast('Voice input was not available');e.voice.onclick=()=>recognition.start();}else{e.voice.disabled=true;e.voice.title='Voice input is not supported by this browser';}
e.speak.onclick=()=>{const latest=[...e.messages.querySelectorAll('.message-row.assistant .message-content')].pop();if(latest&&window.speechSynthesis){window.speechSynthesis.cancel();window.speechSynthesis.speak(new SpeechSynthesisUtterance(latest.textContent));}};

(async()=>{
  try{
    applyTheme(localStorage.getItem("simplechat-theme-v2")||"dark");if(!await authenticate())return;await loadList();
    state.conversations.length?await openConversation(state.conversations[0].id):await createConversation();
  }catch(error){
    e.messages.innerHTML="";
    const section=document.createElement("section");section.className="welcome";
    const heading=document.createElement("h2");heading.textContent="Application error";
    const detail=document.createElement("p");detail.textContent=error.message;
    section.append(heading,detail);e.messages.append(section);
  }
})();
