function readSettings(success, error){
    // This function should probably be in a ScraperWiki-supplied js library.
    // It calls a success callback with a settings object from the window hash if present,
    // or calls an error callback with an error message if something goes wrong.
    if(window.location.hash == ''){
        return error('window.location.hash not supplied')
    }
    hash = window.location.hash.substr(1);
    try {
        settings = JSON.parse(decodeURIComponent(hash));
    } catch(e) {
        return error('window.location.hash is invalid JSON')
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

$(function(){
    readSettings(function(settings){
        console.log(settings)
    }, function(error){
        if(error=='window.location.hash not supplied'){
            showAlert('Which dataset do you want to visualise?', 'You didn&rsquo;t supply a JSON object of settings in the URL hash. Are you sure you followed the right link?');
        } else if(error=='window.location.hash is invalid JSON'){
            showAlert('Could not read settings from URL hash!', 'The settings supplied in your URL hash are not a valid JSON object. Are you sure you followed the right link?');
        } else {
            showAlert('Oh noes!', 'Something mysterious went wrong when we tried to load your dataset settings. Are you sure you followed the right link?')
        }
    })
})