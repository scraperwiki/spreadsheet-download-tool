function localSql(sql, success, error) {
  var settings = scraperwiki.readSettings()
  options = {
    url: "" + settings.source.url + "/sql/",
    type: "GET",
    dataType: "json",
    data: {
      q: sql
    }
  }
  if (success != null) {
    options.success = success
  }
  if (error != null) {
    options.error = error
  }
  return $.ajax(options)
}


$(function(){

  console.log(scraperwiki.readSettings())

  localSql('SELECT * FROM "_state" ORDER BY "filename" DESC').done(function(data){
    console.log(data)
  }).fail(function(x, y, z){
    x.responseText, y, z
  })

})
