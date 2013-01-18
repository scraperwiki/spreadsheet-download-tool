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
        $.ajax({
            url: '../exec',
            type: 'POST',
            data: {
                apikey: view_apikey,
                cmd: 'cd;./extract.py ' + dataset_box_url
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
    readSettings(function(settings){
        if('dataset_box_url' in settings && 'view_apikey' in settings){
            prepareDownload(settings.dataset_box_url, settings.apikey).done(function(urls){
                $('body').append('<p>Your spreadsheet is ready!</p>')
                $ul = $('<ul>')
                $.each(data, function(i, file){
                    $ul.append('<li><a href="' + file + '">' + file + '</a></li>')
                    $('<iframe>').attr('src', file).hide().appendTo('body');
                })
                $ul.appendTo('body')
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
