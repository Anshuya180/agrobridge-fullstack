/* Forecasts now come from the machine-learning model on the server (see ml.py). */
const CROPS={mustard:[0,0,'🌼'],wheat:[0,0,'🌾'],rice:[0,0,'🍚'],soybean:[0,0,'🫘'],maize:[0,0,'🌽']};
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],mon=d=>MON[d.getMonth()]+' '+d.getFullYear(),fmt=n=>Number(n).toLocaleString('en-IN');
const _fc={};
function forecast(c){if(_fc[c])return _fc[c];const d=call('GET','forecast?crop='+c);
 return _fc[c]={cur:d.current,advice:d.advice,note:d.note,hist:d.history.map(x=>({price:x.price})),
  fc:d.forecast.map(x=>({d:new Date(+x.month.slice(0,4),+x.month.slice(5,7)-1,1),price:x.price,low:x.low,high:x.high}))}}
/* Sample reference tables (move to the backend and feed with UN Comtrade / freight data later). */
const EXPORT=[['UAE',700],['Nepal',690],['Bangladesh',686],['Ghana',615],['Belgium',665]],ORIG={India:[690,{Ghana:95,UAE:60,Belgium:110}],Canada:[640,{Ghana:150,UAE:170,Belgium:120}],Russia:[610,{Ghana:140,UAE:120,Belgium:90}],Ukraine:[600,{Ghana:130,UAE:115,Belgium:80}]},DUTY={Ghana:.1,UAE:.05,Belgium:.09};
