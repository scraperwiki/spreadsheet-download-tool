function readSettings(success, error){
    // This function should probably be in a ScraperWiki-supplied js library.
    // It calls a success callback with a settings object from the window hash if present,
    // or calls an error callback with an error message if something goes wrong.
    if(window.location.hash == ''){
        return error('URL #fragment not supplied')
    }
    hash = window.location.hash.substr(1);
    try {
        settings = JSON.parse(decodeURIComponent(hash));
    } catch(e) {
        return error('URL #fragment is invalid JSON')
    }
    return success(settings)
}

function showAlert(title, message, level){
    // [title] and [message] should be html strings. The first is displayed in bold.
    // If [level] is a truthful value, the alert is printed in red.
    level = level || 0;
    var $div = $('<div>').addClass('alert').html('<button type="button" class="close" data-dismiss="alert">×</button>');
    $div.append('<strong>' + title +'</strong> ' + message)
    if(level){
        $div.addClass('alert-error');
    }
    $div.prependTo('body');
}

function prepareDownload(dataset_box_url, view_apikey){
    // This returns a jQuery deferred object, so you can chain
    // .done(), .fail() and .always() methods onto it.
    return $.Deferred(function(deferredObject) {
        // Call this box's exec endpoint, to execute the (Python) extraction script
        var thisBoxName = window.location.pathname.split('/')[1]
        $.ajax({
            url: '/' + thisBoxName + '/exec',
            type: 'POST',
            dataType: 'json',
            data: {
                apikey: view_apikey,
                cmd: 'cd;./spreadsheet-download-tool/extract.py ' + dataset_box_url
            }
        }).done(function(data){
            // Data should be a JSON list of spreadsheet urls,
            // provided by the completed extraction script
            if(typeof(data)=='object'){
                deferredObject.resolve(data)
            } else {
                deferredObject.reject('Dataset extraction failed: ' + String(data))
            }
        }).fail(function(jqXHR, textStatus, errorThrown){
            deferredObject.reject('Ajax call failed: ' + textStatus + ' ' + errorThrown)
        })
    })
}

$(function(){
    view_url = location.protocol + '//' + location.host + '/' + location.pathname.split('/')[1] + '/' + location.pathname.split('/')[2]
    readSettings(function(settings){
        if('dataset_box_url' in settings && 'view_apikey' in settings){
            prepareDownload(settings.dataset_box_url, settings.view_apikey).done(function(urls){
                $('p.loading').remove()
                $success = $('<div class="container">')
                // This will need rewording when urls list contains more than one file (see upcoming card!!)
                $success.append('<p class="lead">Your spreadsheet is downloading!</p>')
                $success.append('<p class="alternative">Alernatively, copy and paste this link to share the spreadsheet with other people:</p>')
                $.each(urls, function(i,file){
                  $('<input>').attr('type', 'text').on('focus', function(){
                    $(this).select()
                  }).on('mouseup', function(e){
                    e.preventDefault() // a fix for webkit not letting you .select() text in an input
                  }).val(view_url + '/http/' + file).appendTo($success)
                  $('<iframe>').attr('src', view_url + '/http/' + file).hide().appendTo('body');
                })
                $success.appendTo('body')
            }).fail(function(error){
                showAlert('Something went wrong', 'Your download could not be prepared. The following error was generated when we tried: &ldquo;' + error + '&rdquo;')
            })
        } else if('view_apikey' in settings){
            showAlert('Which dataset do you want to visualise?', 'You supplied a JSON object in the URL #fragment, but it doesn&rsquo;t contain a &ldquo;dataset_box_url&rdquo; key-value pair. Are you sure you followed the right link?', true)
        } else if('dataset_box_url' in settings){
            showAlert('What is your ScraperWiki API key?', 'You supplied a JSON object in the URL #fragment, but it doesn&rsquo;t contain a &ldquo;view_apikey&rdquo; key-value pair. Are you sure you followed the right link?', true)
        } else {
            showAlert('We need to know more information!', 'You supplied a JSON object in the URL #fragment, but it contains neither a &ldquo;dataset_box_url&rdquo; nor a &ldquo;view_apikey&rdquo;. This tool needs both. Are you sure you followed the right link?', true)
        }
    }, function(error){
        if(error=='URL #fragment not supplied'){
            showAlert('Which dataset do you want to visualise?', 'You didn&rsquo;t supply a JSON object of settings in the URL #fragment. Are you sure you followed the right link?', true)
        } else if(error=='URL #fragment is invalid JSON'){
            showAlert('Could not read settings from URL #fragment!', 'The settings supplied in your URL #fragment are not a valid JSON object. Are you sure you followed the right link?', true)
        } else {
            showAlert('Oh noes!', 'Something mysterious went wrong when we tried to load your dataset settings. Are you sure you followed the right link?', true)
        }
    })
})
