(function(){
  var rowsEl=document.getElementById('rows'), q=document.getElementById('q'), cnt=document.getElementById('count');
  function num(n){return (n||0).toLocaleString();}
  function money(n){return (n||0).toFixed(2);}
  function render(){
    var term=(q.value||'').toLowerCase();
    var data=window.DEVS.filter(function(d){return !term||d.name.toLowerCase().indexOf(term)>=0;})
      .sort(function(x,y){return y.tx-x.tx;});
    rowsEl.innerHTML=data.map(function(d){
      return '<tr onclick="location.href=\'d/'+d.slug+'.html\'" style="cursor:pointer">'+
        '<td class="name"><a href="d/'+d.slug+'.html">'+d.name+'</a></td>'+
        '<td class="num">'+num(d.tx)+'</td><td class="num">'+money(d.val23)+'</td>'+
        '<td class="num">'+num(d.nproj)+'</td></tr>';
    }).join('');
    cnt.textContent=data.length+' developers';
  }
  q.addEventListener('input',render);
  render();
})();
