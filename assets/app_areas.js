(function(){
  var rowsEl=document.getElementById('rows'), q=document.getElementById('q'), cnt=document.getElementById('count');
  var filter='all';
  function chip(s,t){return '<span class="chip '+s+'">'+t+'</span>';}
  function money(n){return (n||0).toFixed(2);}
  function num(n){return (n||0).toLocaleString();}
  function render(){
    var term=(q.value||'').toLowerCase();
    var data=window.AREAS.filter(function(a){
      if(filter==='ok'&&a.status!=='ok')return false;
      if(filter==='warn'&&a.status!=='warn')return false;
      if(filter==='corrected'&&!a.corrected)return false;
      if(term&&!(a.dld.toLowerCase().indexOf(term)>=0||(a.kname||'').toLowerCase().indexOf(term)>=0))return false;
      return true;
    }).sort(function(x,y){return y.tx-x.tx;});
    rowsEl.innerHTML=data.map(function(a){
      var c=chip(a.status,a.stxt)+(a.corrected?' '+chip('fix','Corrected'):'');
      return '<tr onclick="location.href=\'a/'+a.slug+'.html\'" style="cursor:pointer">'+
        '<td class="name"><a href="a/'+a.slug+'.html">'+a.dld+'</a></td>'+
        '<td>'+(a.kname||'')+(a.kid?' <span class="muted">#'+a.kid+'</span>':'')+'</td>'+
        '<td>'+c+'</td><td class="num">'+num(a.tx)+'</td><td class="num">'+money(a.val23)+'</td></tr>';
    }).join('');
    cnt.textContent=data.length+' areas';
  }
  q.addEventListener('input',render);
  Array.prototype.forEach.call(document.querySelectorAll('.filterbtn'),function(b){
    b.addEventListener('click',function(){
      document.querySelector('.filterbtn.active').classList.remove('active');
      b.classList.add('active');filter=b.dataset.f;render();
    });
  });
  render();
})();
