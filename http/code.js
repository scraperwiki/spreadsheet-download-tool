var issueTracker = 'https://github.com/scraperwiki/spreadsheet-download-tool/issues'

var reportAjaxError = function(jqXHR, textStatus, errorThrown, source){
  console.log(source + ' returned an ajax error:', jqXHR, textStatus, errorThrown)
  scraperwiki.alert('There was a problem reading your dataset', 'The <code>' + source + '</code> function returned an ajax ' + textStatus + ' error. <a href="' + issueTracker + '" target="_blank">Click here to log this as a bug.</a>', true)
}

var getDatasetTablesAndGrids = function(cb){
  // calls the `cb` callback with an object containing
  // lists of tables and grids in the parent dataset
  // eg: {"tables": [{"id":"_grids", "name":"_grids"}], "grids": [...]}
  var tablesAndGrids = {
    "tables": [],
    "grids": []
  }
  scraperwiki.dataset.sql.meta().fail(function(jqXHR, textStatus, errorThrown){
    reportAjaxError(jqXHR, textStatus, errorThrown, 'scraperwiki.dataset.sql.meta()')
    cb(tablesAndGrids)
  }).done(function(meta){
    console.log('dataset contains', meta.table.length, 'tables:', meta.table)
    if(meta.table.length == 0){
      scraperwiki.alert('Your dataset has no tables', 'This shouldn&rsquo;t really be an error. We should handle this more gracefully.')
      cb(tablesAndGrids)
    } else {
      $.each(meta.table, function(table_name, table_meta){
        tablesAndGrids.tables.push({"id": table_name, "name": table_name})
      })
      if('_grids' in meta.table){
        scraperwiki.dataset.sql('SELECT * FROM _grids').fail(function(jqXHR, textStatus, errorThrown){
          reportAjaxError(jqXHR, textStatus, errorThrown, 'scraperwiki.dataset.sql()')
          cb(tablesAndGrids)
        }).done(function(grids){
          $.each(grids, function(i, grid){
            tablesAndGrids.grids.push({"id": grid.checksum, "name": grid.title})
          })
          cb(tablesAndGrids)
        })
      }
    }
  })
}

var renderListItem = function(id, filename, state, timestamp){
  // `id` should be a unique id for the table/grid
  // `name` should be a filename (either generated, or prospective)
  // `state` should be either "generated", "generating" or "waiting"
  // `timestamp` should (optionally) be an ISO-8601 creation date for the file
  var $li = $('<li>')
  $li.attr('data-id', id)
  var $a = $('<a>')
  $a.append('<span class="filename">' + filename + '</span>')
  if(state == 'generated'){
    $a.addClass(filename.split('.').pop()) // gets everything after the last dot (ie: extension)
    if(typeof timestamp === 'string'){
      $a.attr('data-timestamp', timestamp)
      $a.append('<span class="state">' + moment(timestamp).add(1, 'hour').fromNow() + '</span>')
    }
    $a.attr('href', scraperwiki.readSettings().target.url + '/http/' + filename)
  } else if(state == 'generating'){
    $a.addClass('generating')
    $a.append('<span class="state">Generating</span>')
  } else {
    $a.addClass('waiting')
    $a.append('<span class="state">Waiting</span>')
  }
  $li.append($a)
  if($('li[data-id="' + id + '"]').length){
    // a list item for this file already exists, so replace it
    $('li[data-id="' + id + '"]').replaceWith($li)
  } else {
    // this is a new file, so append it to the list
    $('#files').append($li)
  }
}

$(function(){

  getDatasetTablesAndGrids(function(tablesAndGrids){
    $.each(tablesAndGrids.tables, function(i, table){
      if(i==0){
        renderListItem(table.id, table.name + '.csv', 'generated', moment().subtract('hour', 2).format())
      } else if(i==1){
        renderListItem(table.id, table.name + '.csv', 'generating')
      } else {
        renderListItem(table.id, table.name + '.csv', 'waiting')
      }
    })
    renderListItem('all_tables', 'all_tables.csv', 'waiting')
    $('p.controls').show()
  })

})
