(function($){
    // module tracks the tab we are currently in.
    // This enables us to show the contents of the page using the class name module_0, module_1, module_2 etc
    let module = 0
    let newspapersheet_form = $('#newspapersheet_form').length;
    let radiosheet_form = $('#radiosheet_form').length;
    let televisionsheet_form = $('#televisionsheet_form').length;
    let internetnewssheet_form = $('#internetnewssheet_form').length;
    let twittersheet_form = $('#twittersheet_form').length;


    if(newspapersheet_form > 0 || twittersheet_form > 0 || radiosheet_form > 0 || televisionsheet_form > 0 || internetnewssheet_form > 0){
        $(document).ready(function() {
            module = $('.changeform-tabs li.selected').index();
            let last_tab = $('.changeform-tabs li:last-child').hasClass('selected');
            if(last_tab) {
                $('input[name=_addanother]').show()
                $('input[name=_save]').show()
            }else{
                $('input[name=_addanother]').hide()
                $('input[name=_save]').hide()
            }
        });
        $('body').click(function(e) {
            setTimeout(function() {
                module = $('.changeform-tabs li.selected').index();
                let last_tab = $('.changeform-tabs li:last-child').hasClass('selected');
                if(last_tab) {
                $('input[name=_addanother]').show()
                $('input[name=_save]').show()
                }else{
                    $('input[name=_addanother]').hide()
                    $('input[name=_save]').hide()
                }
            }, 0)            
        });
        $('input[name=_continue]').click((function(e) {
            e.preventDefault();
            // Move to next tab unless we are on the last tab
            if ($('.changeform-tabs li.selected:last-child').length == 0){
                $('.changeform-tabs li.selected').removeClass('selected').next().addClass('selected');
                $(`.module_${module}`).removeClass('selected');
                $(`.module_${module+1}`).addClass('selected');
            }
        }));
    }
}(jet.jQuery));
