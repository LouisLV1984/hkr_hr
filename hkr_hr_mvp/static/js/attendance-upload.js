(() => {
 const form = document.querySelector("[data-attendance-upload-form]");
 if (!form) return;
 const input = form.querySelector('[type="file"]'), button = form.querySelector('[type="submit"]');
 const labels = JSON.parse(document.getElementById("upload-queue-labels").textContent);
 let queue = [], batch = null, destination = null, busy = false;
 const list = document.createElement("ul"); list.className="upload-file-queue"; form.after(list);
 const open = document.createElement("a"); open.className="primary-btn"; open.hidden=true; open.textContent=labels.open; list.after(open);
 input.addEventListener("change", () => {
   queue = [...input.files].map(file => ({file, done:false, status:labels.pending})); batch=null; destination=null; open.hidden=true; draw();
 });
 function draw() {
   list.replaceChildren(...queue.map(item => {
     const li = document.createElement("li"); li.textContent=item.file.name + " · " + item.status; return li;
   }));
 }
 form.addEventListener("submit", async event => {
   event.preventDefault(); event.stopImmediatePropagation(); if(busy) return;
   if(!queue.length) queue=[...input.files].map(file => ({file,done:false,status:labels.pending}));
   const defaults = new FormData(form); defaults.delete("files");
    busy=true; button.disabled=true; input.disabled=true;
   try {
     for(const item of queue.filter(i=>!i.done)) {
       item.status=labels.uploading; draw();
       const data=new FormData(); defaults.forEach((value,key)=>data.append(key,value)); data.append("files",item.file);
       if(batch) data.set("batch_id",batch);
       try {
         const response=await fetch(form.action,{method:"POST",body:data,headers:{"X-HKR-Profile-Editor":"1","X-HKR-Upload-Queue":"1"}});
         const result=await response.json();
         if(!response.ok || !result.batch_id) throw Error((result.errors||[labels.failed]).join(" · "));
         batch=result.batch_id; destination=result.redirect; item.done=true; item.status=labels.done;
       } catch(error) { item.status=error.message || labels.failed; }
       draw();
     }
     if(destination){open.href=destination;open.hidden=false;}
     if(queue.every(i=>i.done)) location.assign(destination);
     else button.textContent=labels.retry;
   } finally {busy=false;button.disabled=false;input.disabled=false;}
 },true);
})();
