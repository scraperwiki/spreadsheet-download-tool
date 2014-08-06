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
        scraperwiki.dataset.sql('SELECT * FROM _grids ORDER BY number').fail(function(jqXHR, textStatus, errorThrown){
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
  scraperwiki.tool.sql('SELECT * FROM _state_files').done(function(files){
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
      var xlsxUrl = datasetUrl + "/cgi-bin/xlsx/"
      li = ('<li><a class="xlsx" href="' + xlsxUrl + '" target="_blank"><span class="filename">'+
            'all_tables.xlsx</span><span class="state">live</span></a></li>')
      $('#archives').append(li)

    }
  })

  datasetUrl = scraperwiki.readSettings().target.url
  var xlsxUrl = datasetUrl + "/cgi-bin/xlsx/"
  var csvUrl = datasetUrl + "/cgi-bin/csv/"

  scraperwiki.sql.meta().done(function(metadata){
    $('#feeds').show()
    $('#loading').hide()

    $.each(metadata.table, function(name) {
      if (/^_/.test(name)) {
        return
      }

      li = ('<li><a class="csv" href="' + csvUrl + name + '.csv" target="_blank"><span class="filename">'+
            name + '.csv</span><span class="state">live</span></a></li>')
      $('#files').append(li)

      li = ('<li><a class="xlsx" href="' + xlsxUrl + name + '" target="_blank"><span class="filename">'+
            name + '.xlsx</span><span class="state">live</span></a></li>')
      $('#archives').append(li)
    })

    $.each(metadata.grid, function(thisGrid, a) {
      if (!/^_/.test(thisGrid)) {
          var name = 'page_' + String(a.number)
          li = ('<li><a class="xlsx" href="' + xlsxUrl + name + '" target="_blank"><span class="filename">'+
                name + '.xlsx</span><span class="state">live</span></a></li>')
          $('#archives').append(li)
      }
    })
  })

  $('#refresh').on('click', refresh_click)

})
