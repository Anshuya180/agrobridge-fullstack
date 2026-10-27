/* Talks to the FastAPI backend. Uses synchronous requests so the existing UI code works unchanged (fine for an MVP). */
const BASE=location.protocol==='file:'?'http://localhost:8000':'';
function call(method,path,body){const x=new XMLHttpRequest();x.open(method,BASE+'/api/'+path,false);x.setRequestHeader('Content-Type','application/json');
 const t=localStorage.ab_token;if(t)x.setRequestHeader('Authorization','Bearer '+t);
 try{x.send(body?JSON.stringify(body):null)}catch(e){throw Error('Cannot reach the server. Is the backend running?')}
 let d={};try{d=JSON.parse(x.responseText)}catch(e){}
 if(x.status>=400)throw Error(typeof d.detail=='string'?d.detail:'Please check your inputs');return d}
const save=d=>{localStorage.ab_token=d.token;localStorage.ab_user=JSON.stringify(d.user);return d.user};
const API={
 me:()=>JSON.parse(localStorage.ab_user||'null'),
 register:b=>save(call('POST','register',b)),login:b=>save(call('POST','login',b)),
 logout:()=>{localStorage.removeItem('ab_token');localStorage.removeItem('ab_user')},
 listings:()=>call('GET','listings'),allListings:()=>call('GET','listings?all=1'),mine:()=>call('GET','listings/mine'),
 addListing:(u,b)=>call('POST','listings',b),offers:()=>call('GET','offers/mine'),
 offer:(u,l,b)=>call('POST','offers',{lid:l.id,qty:b.qty,price:b.price}),accept:id=>call('POST','offers/'+id+'/accept',{})};
