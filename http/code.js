function humanOldness(diff){
  // diff should be a value in seconds
  var  day_diff = Math.floor(diff / 86400)
  if ( isNaN(day_diff) || day_diff < 0 || day_diff >= 31 )
    return
  return day_diff == 0 && (
      diff < 60 && "brand new" ||
      diff < 120 && "1 minute old" ||
      diff < 3600 && Math.floor( diff / 60 ) + " minutes old" ||
      diff < 7200 && "1 hour old" ||
      diff < 86400 && Math.floor( diff / 3600 ) + " hours old") ||
    day_diff == 1 && "1 day old" ||
    day_diff < 7 && day_diff + " days old" ||
    day_diff < 31 && Math.ceil( day_diff / 7 ) + " weeks old"
}

// http://stackoverflow.com/questions/280634
String.prototype.endsWith = function(suffix) {
    return this.indexOf(suffix, this.length - suffix.length) !== -1
}

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

function showFiles(files){
  // files should be a list of objects, containing rowids, filenames and ages:
  // [ {rowid: 2, filename: 'test.csv', age: 3600}, {…}, … ]
  var $ul = $('ul.nav')
  $('li', $ul).each(function(){
    var li = $(this)
    var id = li.attr('id')
    var found = false
    $.each(files, function(i, file){
      if('file_' + file.rowid == id){
        found = true
      }
    })
    if(!found){
      li.remove()
    }
  })
  $.each(files, function(i, file){
    var elementId = '#file_' + file.rowid
    var loading = (file.age == '' || file.age == null)
    var needToCreate = !($(elementId).length)
    var icon = file.filename.endsWith('csv') ? 'csv.png' : 'xls.png'

    if(needToCreate) {
      $ul.append('<li id="file_'+ file.rowid +'"><a><img src="'+ icon +'" width="16" height="16"> '+ file.filename +' <span class="muted pull-right"></span></a></li>')
    }

    if(loading){
      var timeOrLoading = 'Creating <img src="loading.gif" width="16" height="16">'
      $(elementId + ' a').addClass('loading').removeAttr('href')
    } else {
      var timeOrLoading = humanOldness(file.age)
      $(elementId + ' a').removeClass('loading').attr('href', file.filename)
    }

    if($(elementId + ' span.muted').html() != timeOrLoading){
      console.log($(elementId + ' span.muted').html(), timeOrLoading)
      $(elementId + ' span.muted').html(timeOrLoading)  // update the time
    }
  })
}

function trackProgress(){
  localSql('SELECT rowid, filename, STRFTIME("%s", "now") - STRFTIME("%s", created) AS age FROM _state ORDER BY filename ASC').done(function(files){
    showFiles(files)
  }).fail(function(x, y, z){
    if(x.responseText.match(/database file does not exist/) != null){
      regenerate()
    } else {
      $(".alert").remove()
      scraperwiki.alert('Error contacting ScraperWiki API, please check you are online.', x.responseText + " " + z, 1)
    }
  })

  localSql('SELECT message from _error').done(function(messages){
    $.each(messages, function(i, message){
      $(".alert").remove()
      scraperwiki.alert('Error running extract.py', message.message, 1)
    })
  })
  // don't try and handle errors in getting an error message, as we're screwed
  // anyway then and probably the _state query above will have failed too
}

function regenerate(){

  scraperwiki.exec('echo "' + scraperwiki.readSettings().target.url + '" > ~/dataset_url.txt; ' + 
                   'echo "started"; run-one tool/extract.py &> log.txt &')
  $('#regenerate').attr('disabled', true)
}

$(function(){

  $(document).on('click', '#regenerate', regenerate)

  trackProgress()
  poll = setInterval(trackProgress, 2000)

})
