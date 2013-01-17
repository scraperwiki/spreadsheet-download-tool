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

$(function(){
    readSettings(function(settings){
        console.log(settings)
    }, function(error){
        console.warn(error)
    })
})