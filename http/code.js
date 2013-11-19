window.issueTracker = 'https://github.com/scraperwiki/spreadsheet-download-tool/issues'

var reportAjaxError = function(jqXHR, textStatus, errorThrown, source){
  console.log(source + ' returned an ajax error:', jqXHR, textStatus, errorThrown)
  var message = 'The <code>' + source + '</code> function returned an ajax ' + textStatus + ' error.'
  if(typeof jqXHR.responseText == 'string'){
    message += ' The response text was: <pre>' + $.trim(jqXHR.responseText) + '</pre>'
  }
  message += '<a href="' + issueTracker + '" target="_blank">Click here to log this as a bug.</a>'
  scraperwiki.alert('There was a problem reading your dataset', message, true)
}

var resetGlobalVariables = function(){
  window.tablesAndGrids = {
    "tables": [],
    "grids": []
  }
  window.files = []
  window.timer = null
}

var getDatasetTablesAndGrids = function(cb){
  // calls the `cb` callback with an object containing
  // lists of tables and grids in the parent dataset
  // eg: {"tables": [{"id":"_grids", "name":"_grids"}], "grids": [...]}
  console.log('getDatasetTablesAndGrids()')
  scraperwiki.dataset.sql.meta().fail(function(jqXHR, textStatus, errorThrown){
    reportAjaxError(jqXHR, textStatus, errorThrown, 'scraperwiki.dataset.sql.meta()')
    cb(window.tablesAndGrids)
  }).done(function(meta){
    if(meta.table.length == 0){
      console.log('getDatasetTablesAndGrids() ... meta.table.length == 0')
      scraperwiki.alert('Your dataset has no tables', 'This shouldn&rsquo;t really be an error. We should handle this more gracefully.')
      cb(window.tablesAndGrids)
    } else {
      console.log('getDatasetTablesAndGrids() ... found', _.keys(meta.table).length, 'tables:', _.keys(meta.table).join(', '))
      // add tables to window.tablesAndGrids
      $.each(meta.table, function(table_name, table_meta){
        // ignore tables beginning with an underscore
        if(table_name.indexOf('_') != 0){
          window.tablesAndGrids.tables.push({"id": table_name, "name": table_name})
        }
      })
      if('_grids' in meta.table){
        // add grids to window.tablesAndGrids
        console.log('getDatasetTablesAndGrids() ... found _grids table')
        scraperwiki.dataset.sql('SELECT * FROM _grids').fail(function(jqXHR, textStatus, errorThrown){
          reportAjaxError(jqXHR, textStatus, errorThrown, 'scraperwiki.dataset.sql()')
          cb(window.tablesAndGrids)
        }).done(function(grids){
          console.log('getDatasetTablesAndGrids() ... found', grids.length, 'grids')
          $.each(grids, function(i, grid){
            window.tablesAndGrids.grids.push({"id": grid.checksum, "name": grid.title})
          })
          cb(window.tablesAndGrids)
        })
      } else {
        // no grids: ust return what we've got
        console.log('getDatasetTablesAndGrids() ... no _grids table')
        cb(window.tablesAndGrids)
      }
    }
  })
}

var generateFileList = function(cb){
  // given a load of sources in window.tablesAndGrids, and
  // information from the _state_files SQL table, this function
  // contructs a list of files generated / to be generated
  console.log('generateFileList() from', window.tablesAndGrids.tables.length, 'tables and', window.tablesAndGrids.grids.length, 'grids')
  $.each(window.tablesAndGrids.tables, function(i, table){
    window.files.push({
      'filename': makeFilename(table.name) + '.csv',
      'state': 'waiting',
      'created': null,
      'source_type': 'table',
      'source_id': table.name
    })
  })
  $.each(window.tablesAndGrids.grids, function(i, grid){
    window.files.push({
      'filename': makeFilename(grid.name) + '.csv',
      'state': 'waiting',
      'created': null,
      'source_type': 'table',
      'source_id': grid.id
    })
  })
  window.files.push({
    'filename': 'all_tables.xlsx',
    'state': 'waiting',
    'created': null,
    'source_type': null,
    'source_id': 'all_tables'
  })
  updateFileList(cb)
}

var updateFileList = function(cb){
  console.log('updateFileList() called')
  scraperwiki.tool.sql('SELECT filename, state, created FROM _state_files').done(function(files){
    console.log('updateFileList() got files')
    $.each(files, function(i, file){
      fileRecordToUpdate = _.findWhere(window.files, {'filename':file.filename})
      if(typeof fileRecordToUpdate !== 'undefined'){
        fileRecordToUpdate.state = file.state
        fileRecordToUpdate.created = file.created
      }
    })
    cb() // this callback is usually renderFiles()
  }).fail(function(jqXHR, textStatus, errorThrown){
    console.log('updateFileList() ajax error', jqXHR.responseText, textStatus, errorThrown)
    if(/does not exist/.test(jqXHR.responseText) || /no such table/.test(jqXHR.responseText) || /no such column/.test(jqXHR.responseText)){
      console.log('updateFileList() ... database or table does not exist')
      // kick off regeneration if we're not already running
      console.log('updateFileList() ... kicking off regenerate()')
      regenerate()
      cb() // this callback is usually renderFiles()
    } else {
      reportAjaxError(jqXHR, textStatus, errorThrown, 'scraperwiki.tool.sql("SELECT filename, state, created FROM _state_files")')
    }
  })
}

var renderListItem = function(file){
  // `file.source_id` should be a unique id for the table/grid
  // `file.source_type` should be either "table", "grid", or null
  // `file.filename` should be a filename (either generated, or prospective)
  // `file.state` should be either "generated", "generating" or "waiting"
  // `file.created` should (optionally) be an ISO-8601 creation date for the file
  var $li = $('<li>')
  if(file.source_id == 'all_tables'){
    var $ul = $('#archives')
  } else {
    var $ul = $('#files')
  }
  $li.attr('data-source-id', file.source_id)
  $li.attr('data-source-type', file.source_type)
  var $a = $('<a>')
  $a.append('<span class="filename">' + file.filename + '</span>')
  if(file.state == 'generated'){
    // Gets everything after the last dot (that is, extension).
    var extension = file.filename.split('.').pop()
    $a.addClass(extension)
    if(typeof file.created === 'string'){
      $a.attr('data-timestamp', file.created)
      $a.append('<span class="state">' + moment(file.created).fromNow() + '</span>')
    }
    $a.attr('href', scraperwiki.readSettings().source.url + '/http/' + file.filename)
  } else if(file.state == 'generating') {
    $a.addClass('generating')
    $a.append('<span class="state">Generating</span>')
  } else if(file.state == 'failed') {
    $a.addClass('failed')
    $a.append('<span class="state">Failed</span>')
  } else {
    $a.addClass('waiting')
    $a.append('<span class="state">Waiting</span>')
  }
  $li.append($a)
  if($('li[data-source-id="' + file.source_id + '"]', $ul).length){
    // a list item for this file already exists, so replace it
    $('li[data-source-id="' + file.source_id + '"]', $ul).replaceWith($li)
  } else {
    // this is a new file, so append it to the list
    $ul.append($li)
  }
}

var renderFiles = function(){
  console.log('renderFiles()')
  $.each(window.files, function(i, file){
    renderListItem(file)
  })
  // $('p.controls').show()
}

var makeFilename = function(naughtyString){
  return naughtyString.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9-_.]+/g, '')
}

var saveDatasetUrl = function(cb){
  console.log('saveDatasetUrl()')
  scraperwiki.tool.exec('echo "' + scraperwiki.readSettings().target.url + '" > ~/dataset_url.txt')
  if(typeof cb != 'undefined'){
    cb()
  }
}

var regenerate = function(){
  console.log('regenerate()')
  scraperwiki.tool.exec('echo "started"; run-one tool/create_downloads.py &> log.txt &')
}

var setTimer = function() {
  console.log('setting window.timer interval for checkStatus()')
  if(window.timer === null){
    window.timer = setInterval(checkStatus, 2000)
  }
}

var clearTimer = function(){
  console.log('clearing window.timer interval for checkStatus()')
  clearInterval(window.timer)
}

var checkStatus = function(){
  console.log('checkStatus()')
  var unfinishedFiles = _.reject(window.files, function(file){
    return file.state == 'generated'
  })
  if(unfinishedFiles.length){
    // some files are still outstanding, so check
    // _state_files for updates, and _error for errors
    scraperwiki.tool.sql('select * from _error', function(errors){
      // there was an error!! Stop everything and display it
      var error = errors[0]['message']
      clearTimer()
      if(/DatasetIsEmptyError/.test(error)){
        showEmptyDatasetMessage()
      } else if(/row index \(65536\) not an int in range\(65536\)/.test(error)){
        scraperwiki.alert('An error occurred:', 'One of your tables has more than 65536 rows, and could not be written to the Excel file. Contact hello@scraperwiki.com for help.', true)
      } else {
        scraperwiki.alert('An unexpected error occurred.', 'Contact hello@scraperwiki.com for help.<pre style="margin-top: 7px">' + error + '</pre>', true)
      }
    }, function(jqXHR, textStatus, errorThrown){
      if(/does not exist/.test(jqXHR.responseText) || /no such table/.test(jqXHR.responseText)){
        // no errors table, so we assume everything's ok
        updateFileList(renderFiles)
      }
    })
  } else {
    // no files outstanding, don't bother checking _state_files database
    renderFiles()
  }
}

var resetStatusDatabase = function(cb){
  console.log('resetStatusDatabase()')
  scraperwiki.tool.exec('tool/reset_downloads.py', cb, function(jqXHR, textStatus, errorThrown){
    reportAjaxError(jqXHR, textStatus, errorThrown, 'scraperwiki.tool.exec("tool/reset_downloads.py")')
  })
}

var refresh_click = function(){
  if($('#refresh').is('.refreshing')){
    return false
  }
  $('#refresh').addClass('refreshing')
  resetGlobalVariables()
  resetStatusDatabase(function(){
    getDatasetTablesAndGrids(function(){
      generateFileList(function(){
        $('#refresh').removeClass('refreshing')
        renderFiles()
        regenerate()
      })
    })
  })
}

var showEmptyDatasetMessage = function(){
  $('body').html('<div class="problem"><h4>This dataset is empty.</h4><p>Once your dataset contains data,<br/>your downloads will be generated here.</p></div>')
}

$(function(){

  resetGlobalVariables()

  saveDatasetUrl()

  getDatasetTablesAndGrids(function(){
    if(window.tablesAndGrids.tables.length + window.tablesAndGrids.grids.length == 0){
      showEmptyDatasetMessage()
    } else {
      generateFileList(function(){
        renderFiles()
        setTimer()
      })
    }
  })

  $('#refresh').on('click', refresh_click)

})
