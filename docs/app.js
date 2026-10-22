(() => {
  const products = [
    {sku:'BEAN-250',name:'House Blend Coffee',unit_price:'89.00',quantity:18,reorder_level:8},
    {sku:'MUG-04',name:'Stoneware Mug',unit_price:'145.00',quantity:4,reorder_level:6},
    {sku:'SOAP-02',name:'Cedar Hand Soap',unit_price:'62.50',quantity:11,reorder_level:5},
    {sku:'TEA-18',name:'Rooibos Loose Leaf',unit_price:'74.00',quantity:3,reorder_level:5},
    {sku:'TOWEL-01',name:'Waffle Tea Towel',unit_price:'120.00',quantity:15,reorder_level:4},
    {sku:'JAR-06',name:'Glass Pantry Jar',unit_price:'99.00',quantity:7,reorder_level:5},
  ];
  const activity = [
    {sku:'BEAN-250',name:'House Blend Coffee',kind:'receipt',quantity_delta:12,reference:'PO-1042'},
    {sku:'MUG-04',name:'Stoneware Mug',kind:'sale',quantity_delta:-2,reference:'SALE-006'},
    {sku:'SOAP-02',name:'Cedar Hand Soap',kind:'receipt',quantity_delta:6,reference:'PO-1041'},
  ];
  const money = n => `R${Number(n).toLocaleString('en-ZA',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
  const esc = s => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const low = p => p.quantity <= p.reorder_level;
  const $ = id => document.getElementById(id);
  const els = {productRows:$('productRows'),search:$('search'),view:$('view'),empty:$('empty'),productCount:$('productCount'),lowList:$('lowList'),activity:$('activity'),modal:$('modal'),form:$('form'),fields:$('fields'),formError:$('formError'),modalEyebrow:$('modalEyebrow'),modalTitle:$('modalTitle'),saveAction:$('saveAction')};
  function render(){
    const q=els.search.value.trim().toLocaleLowerCase();
    const shown=products.filter(p=>(els.view.value!=='low'||low(p))&&(!q||`${p.name} ${p.sku}`.toLocaleLowerCase().includes(q)));
    const units=products.reduce((n,p)=>n+p.quantity,0), value=products.reduce((n,p)=>n+p.quantity*Number(p.unit_price),0), lowItems=products.filter(low);
    $('heroUnits').textContent=units;$('heroLow').textContent=lowItems.length;$('heroValue').textContent=money(value);
    $('metricProducts').textContent=products.length;$('metricUnits').textContent=units;$('metricValue').textContent=money(value);$('metricLow').textContent=lowItems.length;
    els.productRows.innerHTML=shown.map(p=>`<tr><td><span class="product-name">${esc(p.name)}</span><span class="product-sub">${low(p)?'Review stock level':'Catalog item'}</span></td><td class="sku">${esc(p.sku)}</td><td>${money(p.unit_price)}</td><td class="qty">${p.quantity}</td><td>${p.reorder_level}</td><td><span class="status ${low(p)?'low':''}">${low(p)?'REORDER':'IN STOCK'}</span></td><td><button class="row-actions" data-stock="${esc(p.sku)}" title="Receive stock">＋</button> <button class="row-actions" data-sell="${esc(p.sku)}" title="Record sale">−</button></td></tr>`).join('');
    els.empty.classList.toggle('hidden',shown.length>0);els.productCount.textContent=`${shown.length} product${shown.length===1?'':'s'}`;
    els.lowList.innerHTML=lowItems.length?lowItems.map(p=>`<div class="low-item"><div><strong>${esc(p.name)}</strong><small>${esc(p.sku)} · reorder at ${p.reorder_level}</small></div><span class="stock-count">${p.quantity} left</span></div>`).join(''):'<div class="all-good">✓ Every item is above its reorder point.</div>';
    els.activity.innerHTML=activity.slice(0,5).map(a=>`<div class="activity-item"><span class="activity-icon ${a.kind}">${a.kind==='sale'?'↗':'↙'}</span><span class="activity-text"><strong>${esc(a.name)}</strong><small>${a.kind==='sale'?'Sale':'Stock received'} · ${esc(a.reference)}</small></span><span class="activity-qty ${a.kind}">${a.quantity_delta>0?'+':''}${a.quantity_delta}</span></div>`).join('')||'<div class="no-activity">No changes recorded yet.</div>';
  }
  const field=(label,name,type='text',required=true,full=false,placeholder='')=>`<div class="field ${full?'full':''}"><label for="f-${name}">${label}</label><input id="f-${name}" name="${name}" type="${type}" ${required?'required':''} ${type==='number'?'min="0" step="1"':''} placeholder="${placeholder}" /></div>`;
  function open(mode,sku=''){
    els.formError.textContent='';els.form.dataset.mode=mode;els.form.dataset.sku=sku;els.fields.innerHTML='';
    if(mode==='product'){els.modalEyebrow.textContent='CATALOG ENTRY';els.modalTitle.textContent='Add a product';els.fields.innerHTML=field('PRODUCT NAME','name','text',true,true,'e.g. Canvas tote')+field('SKU','sku','text',true,false,'TOTE-01')+field('PRICE (R)','price','number',true,false,'99.00')+field('REORDER AT','reorder','number',true,false,'5');els.saveAction.textContent='Add product';}
    if(mode==='receive'||mode==='sale'){const p=products.find(x=>x.sku===sku);els.modalEyebrow.textContent=mode==='sale'?'SALE ENTRY':'STOCK RECEIPT';els.modalTitle.textContent=mode==='sale'?'Record a sale':'Receive stock';els.fields.innerHTML=`<div class="field full"><label for="f-sku">PRODUCT</label><select id="f-sku" name="sku" required>${products.map(x=>`<option value="${esc(x.sku)}" ${x.sku===sku?'selected':''}>${esc(x.name)} · ${esc(x.sku)} (${x.quantity} on hand)</option>`).join('')}</select></div>`+field('QUANTITY','quantity','number',true,false,'1')+(mode==='receive'?field('REFERENCE','reference','text',true,true,'Purchase order or note'):'');els.saveAction.textContent=mode==='sale'?'Record sale':'Receive stock';}
    els.modal.showModal();
  }
  $('addOpen').addEventListener('click',()=>open('product'));$('receiveOpen').addEventListener('click',()=>open('receive',products[0]?.sku));$('saleOpen').addEventListener('click',()=>open('sale',products[0]?.sku));
  els.productRows.addEventListener('click',e=>{const s=e.target.dataset.stock,v=e.target.dataset.sell;if(s)open('receive',s);if(v)open('sale',v)});
  els.search.addEventListener('input',render);els.view.addEventListener('change',render);
  els.form.addEventListener('submit',e=>{if(e.submitter?.value==='cancel')return;e.preventDefault();const data=new FormData(els.form),mode=els.form.dataset.mode;try{
    if(mode==='product'){const sku=String(data.get('sku')).trim(),name=String(data.get('name')).trim(),price=Number(data.get('price')),reorder=Number(data.get('reorder'));if(!/^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$/.test(sku))throw Error('Use 1–40 letters, numbers, dots, underscores or hyphens for the SKU.');if(products.some(p=>p.sku.toLowerCase()===sku.toLowerCase()))throw Error('That SKU already exists.');if(!name||!Number.isFinite(price)||price<0||!Number.isInteger(reorder)||reorder<0)throw Error('Enter a product name, a valid price and a whole-number reorder level.');products.push({sku,name,unit_price:price.toFixed(2),quantity:0,reorder_level:reorder});}
    else{const sku=String(data.get('sku')),qty=Number(data.get('quantity')),p=products.find(x=>x.sku===sku);if(!p||!Number.isInteger(qty)||qty<1)throw Error('Choose a product and enter a whole-number quantity above zero.');if(mode==='sale'&&qty>p.quantity)throw Error(`Only ${p.quantity} units are available.`);if(mode==='sale')p.quantity-=qty;else p.quantity+=qty;activity.unshift({sku,name:p.name,kind:mode==='sale'?'sale':'receipt',quantity_delta:mode==='sale'?-qty:qty,reference:mode==='sale'?`SAMPLE-${String(activity.length+1).padStart(3,'0')}`:String(data.get('reference')).trim()});}
    els.modal.close();render();
  }catch(err){els.formError.textContent=err.message;}});
  render();
})();
