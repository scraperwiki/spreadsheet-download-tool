window.timer = null
window.tablesAndGrids = null
window.files = null
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
}

var getDatasetTablesAndGrids = function(cb){
  // calls the `cb` callback with an object containing
  // lists of tables and grids in the parent dataset
  // eg: {"tables": [{"id":"_grids", "name":"_grids"}], "grids": [...]}
  scraperwiki.dataset.sql.meta().fail(function(jqXHR, textStatus, errorThrown){
    reportAjaxError(jqXHR, textStatus, errorThrown, 'scraperwiki.dataset.sql.meta()')
    cb(window.tablesAndGrids)
  }).done(function(meta){
    if(meta.table.length == 0){
      scraperwiki.alert('Your dataset has no tables', 'This shouldn&rsquo;t really be an error. We should handle this more gracefully.')
      cb(window.tablesAndGrids)
    } else {
      // add tables to window.tablesAndGrids
      $.each(meta.table, function(table_name, table_meta){
        // ignore tables beginning with an underscore
        if(table_name.indexOf('_') != 0){
          window.tablesAndGrids.tables.push({"id": table_name, "name": table_name})
        }
      })
      if('_grids' in meta.table){
        // add grids to window.tablesAndGrids
        scraperwiki.dataset.sql('SELECT * FROM _grids').fail(function(jqXHR, textStatus, errorThrown){
          reportAjaxError(jqXHR, textStatus, errorThrown, 'scraperwiki.dataset.sql()')
          cb(window.tablesAndGrids)
        }).done(function(grids){
          $.each(grids, function(i, grid){
            window.tablesAndGrids.grids.push({"id": grid.checksum, "name": grid.title})
          })
          cb(window.tablesAndGrids)
        })
      } else {
        // no grids: ust return what we've got
        cb(window.tablesAndGrids)
      }
    }
  })
}

var generateFileList = function(cb){
  // given a load of sources in window.tablesAndGrids, and
  // information from the _state SQL table, this function
  // contructs a list of files generated / to be generated
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
    'filename': 'all_tables.xls',
    'state': 'waiting',
    'created': null,
    'source_type': null,
    'source_id': 'all_tables'
  })
  updateFileList(cb)
}

var updateFileList = function(cb){
  scraperwiki.tool.sql('SELECT filename, state, created FROM _state').done(function(files){
    $.each(files, function(i, file){
      fileRecordToUpdate = _.findWhere(window.files, {'filename':file.filename})
      if(typeof fileRecordToUpdate !== 'undefined'){
        fileRecordToUpdate.state = file.state
        fileRecordToUpdate.created = file.created
      }
    })
    cb()
  }).fail(function(jqXHR, textStatus, errorThrown){
    if(/does not exist/.test(jqXHR.responseText) || /no such table/.test(jqXHR.responseText)){
      console.log('first run!')
      regenerate()
    } else if(/no such column/.test(jqXHR.responseText)){
      // the database is in some unexpected state. We can't trust it. Clear all data and rebuild.
      scraperwiki.tool.exec('tool/reset_everything.sh', function(){
        window.location.reload()
      }, function(jqXHR, textStatus, errorThrown){
        reportAjaxError(jqXHR, textStatus, errorThrown, 'scraperwiki.tool.exec("tool/reset_everything.sh")')
      })
    } else {
      reportAjaxError(jqXHR, textStatus, errorThrown, 'scraperwiki.tool.sql("SELECT filename, state, created FROM _state")')
    }
    cb()
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
    $a.addClass(file.filename.split('.').pop()) // gets everything after the last dot (ie: extension)
    if(typeof file.created === 'string'){
      $a.attr('data-timestamp', file.created)
      $a.append('<span class="state">' + moment(file.created).fromNow() + '</span>')
    }
    $a.attr('href', scraperwiki.readSettings().source.url + '/http/' + file.filename)
  } else if(file.state == 'generating'){
    $a.addClass('generating')
    $a.append('<span class="state">Generating</span>')
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
  $.each(window.files, function(i, file){
    renderListItem(file)
  })
  // $('p.controls').show()
}

var makeFilename = function(naughtyString){
  return naughtyString.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9-_.]+/g, '')
}

var saveDatasetUrl = function(cb){
  scraperwiki.tool.exec('echo "' + scraperwiki.readSettings().target.url + '" > ~/dataset_url.txt')
  if(typeof cb != 'undefined'){
    cb()
  }
}

var regenerate = function(){
  scraperwiki.tool.exec('echo "started"; run-one tool/create_downloads.py &> log.txt &')
  window.timer = setInterval(check_status, 2000)
}

var check_status = function(){
  var unfinishedFiles = _.reject(window.files, function(file){
    return file.state == 'generated'
  })
  if(unfinishedFiles.length){
    // some files are still outstanding, so check _state database for updates
    updateFileList(renderFiles)
  } else {
    // no files outstanding, don't bother checking _state database
    renderFiles()
  }
}

var resetStatusDatabase = function(cb){
  scraperwiki.tool.exec('tool/reset_downloads.py', cb, function(jqXHR, textStatus, errorThrown){
    reportAjaxError(jqXHR, textStatus, errorThrown, 'scraperwiki.tool.exec("tool/reset_downloads.py")')
  })
}

var refresh_click = function(){
  if($('#refresh').is('.refreshing')){
    return false
  }
  $('#refresh').addClass('refreshing')
  clearInterval(window.timer)
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

$(function(){

  resetGlobalVariables()

  saveDatasetUrl()

  getDatasetTablesAndGrids(function(){
    generateFileList(function(){
      renderFiles()
    })
  })

  $('#refresh').on('click', refresh_click)

})
