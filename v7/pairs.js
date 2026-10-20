const QX=require('./qx.js');
const fs=require('fs');
const K=JSON.parse(fs.readFileSync('../ref/kline320.json','utf8'));
const I=JSON.parse(fs.readFileSync('../ref/index320.json','utf8'));
const st=QX.indexState(I['sh000001'].bars,10);
const out={state:st,stocks:{}};
for(const q of Object.keys(K)){
  const r=QX.analyzeOne(K[q].bars,st,10);
  if(r) out.stocks[q]=r;
}
fs.writeFileSync('/tmp/js_result.json',JSON.stringify(out));
console.log('state',st.tag,(st.p*100).toFixed(2),'n',st.n,'baseP',(st.baseP*100).toFixed(2));
console.log('stocks',Object.keys(out.stocks).length);
