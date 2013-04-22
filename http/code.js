// Takes an ISO time and returns a string representing how
// long ago the date represents.
function prettyDate(time){
	var date = new Date((time || "").replace(/-/g,"/").replace(/T/g," ")),
		diff = (((new Date()).getTime() - date.getTime()) / 1000),
		day_diff = Math.floor(diff / 86400)
			
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
  // files should be a list of objects, containing filenames and dates:
  // [ {filename: 'test.csv', created: 'YYYY-MM-DDTHH:MM:SS'}, {…}, … ]
  var $ul = $('ul.nav').empty()
  $.each(files, function(i, file){
    var href = ' href="'+ file.filename +'"'
    var time = prettyDate(file.created)
    if(file.filename.endsWith('csv')){
      var icon = 'csv.png'
    } else {
      var icon = 'xlsx.png'
    }
    if(file.created == '' || file.created == null){
      var time = 'Creating <img src="loading.gif" width="16" height="16" />'
      var href = ' class="loading"'
    }
    $ul.append('<li><a'+ href +'><img src="'+ icon +'" width="16" height="16"> '+ file.filename +' <span class="muted pull-right">'+ time +'</span></a></li>')
  })
}

function showControls(files){
  if(files.length == 0){
    $('p.controls').addClass('text-center').html('<img src="loading.gif" width="16" height="16" /> Creating your downloads&hellip;')
  } else {
    $('p.controls').removeClass('text-center').html('<button class="btn btn-small pull-right" id="regenerate">Regenerate all files</button>')
  }
}

function trackProgress(){
  localSql('SELECT filename, STRFTIME("%s", "now") - STRFTIME("%s", created) AS age FROM _state ORDER BY filename ASC').done(function(files){
    showFiles(files)
    showControls(files)
  }).fail(function(x, y, z){
    scraperwiki.alert('Error contacting ScraperWiki API', x.responseText, 1)
  })
}

$(function(){

  $(document).on('click', '#regenerate', function(e){
    scraperwiki.exec('echo "started"; tool/extract.py ' + scraperwiki.readSettings().target.url + ' &> log.txt &', function(data){
      poll = setInterval(trackProgress, 2000)
    })
  })

  trackProgress()

})
