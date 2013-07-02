//
// This file is part of Invenio.
// Copyright (C) 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010 CERN.
//
// Invenio is free software; you can redistribute it and / or
// modify it under the terms of the GNU General Public License as
// published by the Free Software Foundation; either version 2 of the
// License, or (at your option) any later version.
//
// Invenio is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
// General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Invenio; if not, write to the Free Software Foundation, Inc.,
// 59 Temple Place, Suite 330, Boston, MA 02111 - 1307, USA.

$(document).ready(function() {

    // Control 'view more info' behavior in search
    $('[class^=more-]').hide();
    $('[class^=mpid]').click(function() {
        var $this = $(this);
        var x = $this.prop("className");
        $('.more-' + x).toggle();
        var toggleimg = $this.find('img').attr('src');

        if (toggleimg == '../img/aid_plus_16.png') {
            $this.find('img').attr({src:'../img/aid_minus_16.png'});
            $this.closest('td').css('padding-top', '15px');
        } else {
            $this.find('img').attr({src:'../img/aid_plus_16.png'});
            $this.closest('td').css('padding-top', '0px');
        }
        return false;
    });

    // Handle Comments
    if ( $('#jsonForm').length ) {

        $('#jsonForm').ajaxForm({
            // dataType identifies the expected content type of the server response
            dataType:  'json',

            // success identifies the function to invoke when the server response
            // has been received
            success:   processJson
        });

        $.ajax({
            url: '/author/claim/comments',
            dataType: 'json',
            data: { 'pid': $('span[id^=pid]').attr('id').substring(3), 'action': 'get_comments' },
            success: processJson
        });
    }

    // Initialize DataTable
    $('.paperstable').dataTable({
                "bJQueryUI": true,
                "sPaginationType": "full_numbers",
                "aoColumns": [
                        { "bSortable": false,
                          "sWidth": "" },
                        { "bSortable": false,
                          "sWidth": "" },
                        { "sWidth": "" },
			{ "sWidth": "" },
			{ "sWidth": "" },
                        { "sWidth": "120px" },
                        { "sWidth": "320px" }
                ],
                "aLengthMenu": [500],
                'iDisplayLength': 500,
                "fnDrawCallback": function() {
                    $('.dataTables_length').css('display','none');
                }
    });

    $('.reviewstable').dataTable({
                "bJQueryUI": true,
                "sPaginationType": "full_numbers",
                "aoColumns": [
                        { "bSortable": false,
                          "sWidth": "" },
                        { "bSortable": false,
                          "sWidth": "" },
                        { "bSortable": false,
                          "sWidth": "120px" }
                ],
                "aLengthMenu": [500],
                'iDisplayLength': 500,
                "fnDrawCallback": function() {
                    $('.dataTables_length').css('display','none');
                }
    });

    // search box
    if ( $('#personsTable').length ) {
        // bind retrieve papers ajax request
        $('[class^=mpid]').on('click', function(event){
            if ( !$(this).siblings('.retreived_papers').length) {
                var pid = $(this).closest('tr').attr('id').substring(3); // e.g pid323
                var data = { 'requestType': "getPapers", 'personId': pid.toString()};
                var errorCallback = onRetrievePapersError(pid);
                $.ajax({
                    dataType: 'json',
                    type: 'POST',
                    url: '/author/claim/search_box_ajax',
                    data: {jsondata: JSON.stringify(data)},
                    success: onRetrievePapersSuccess,
                    error: errorCallback,
                    async: true
                });
                event.preventDefault();
            }
        });
        // create ui buttons
        //$('.confirmlink').button();//#new_person_link,
        //$("#searchform :input").attr("disabled",true);
        // gResultsPerPage = 3;
        // gCurPage = 1;
        // showPage(gCurPage);
        var columns = {};
        $('#personsTable th').each(function(index) {
            columns[$(this).attr('id')] = index;
        });
         // var targets = [3,4,5,6];
         var targets = [columns['IDs'], columns['Papers'], columns['Link']];
         if (columns['Action'] !== undefined) {
            targets.push(columns['Action']);
         }
         if (columns['Merge'] !== undefined) {
            targets.push(columns['Merge']);
         }
        var pTable = $('#personsTable').dataTable({
                "bJQueryUI": true,
                "sPaginationType": "full_numbers",
                "aoColumnDefs": [
                    { "bSortable": false, "aTargets": targets },
                    { "bSortable": true, "aTargets": [columns['Number'], columns['Identifier'], columns['Names']] },
                    { "sType": "numeric", "aTargets": [columns['Number']] },
                    { "sType": "string", "aTargets": [columns['Identifier'], columns['Names']] }
                    ],
                "aaSorting": [[columns['Number'],'asc']],
                "aLengthMenu": [[5, 10, 20, -1], [5, 10, 20 , "All"]],
                "iDisplayLength": 5,
                "oLanguage": {
                    "sSearch": "Filter: "
                }
        });
        // draw first page
        onPageChange();
        // on page change
        $(pTable).bind('draw', function() {
            onPageChange();
        });
    }

    if ( $('.idsAssociationTable').length ) {
        var idTargets = [1,2];
        if ( $('#idsAssociationTableClaim').length ) {
            idTargets.push(3);
        }
        $('.idsAssociationTable').dataTable({
                "bJQueryUI": true,
                "sPaginationType": "full_numbers",
                "aoColumnDefs": [
                    { "bSortable": true, "aTargets": [0] },
                    { "bSortable": false, "aTargets": idTargets },
                    { "sType": "string", "aTargets": [0] }
                    ],
                "aaSorting": [[0,'asc']],
                "iDisplayLength": 5,
                "aLengthMenu": [5, 10, 20, 100, 500, 1000],
                "oLanguage": {
                    "sSearch": "Filter: "
                }
        });
        $('.idsAssociationTable').siblings('.ui-toolbar').css({ "width": "45.4%", "font-size": "12px" });
    }

    if (typeof gMergeProfile !== 'undefined' ) {
        // initiate merge list's html from javascript/session
        $('#primaryProfile').parent().replaceWith('<li><a id=\"primaryProfile\" href=\"' + gMergeProfile +
        '\" target=\"_blank\">' + gMergeProfile + '</a> <strong>(primary profile)</strong></li>');
        $('.addToMergeButton[name="' + gMergeProfile + '"]').prop('disabled','disabled');
        for(var profile in gMergeList) {
            createProfilesHtml(gMergeList[profile]);
            $('.addToMergeButton[name="' + gMergeList[profile] + '"]').prop('disabled','disabled');
        }
        $('.addToMergeButton').on('click', function(event) {
            onAddToMergeClick(event, $(this));
        });
    }

    if ($('#autoclaim').length) {
            var data = { 'personId': gPID.toString()};
            var errorCallback = onRetrieveAutoClaimedPapersError(gPID);
            $.ajax({
                dataType: 'json',
                type: 'POST',
                url: '/author/claim/generate_autoclaim_data',
                data: {jsondata: JSON.stringify(data)},
                success: onRetrieveAutoClaimedPapersSuccess,
                error: errorCallback,
                async: true
            });
    }

    // Activate Tabs
    $("#aid_tabbing").tabs();

    // Style buttons in jQuery UI Theme
	//$(function() {
	//	$( "button, input:submit, a", ".aid_person" ).button();
	//	$( "a", ".demo" ).click(function() { return false; });
	//});

    // Show Message
    $(".ui-alert").fadeIn("slow");
    $("a.aid_close-notify").each(function() {
	$(this).click(function() {
            $(this).parents(".ui-alert").fadeOut("slow");
            return false;
        } );
    });

    // Set Focus on last input field w/ class 'focus'
    $("input.focus:last").focus();

    // Select all
    $("A[href='#select_all']").click( function() {
        $('input[name=selection]').attr('checked', true);
        return false;
    });

    // Select none
    $("A[href='#select_none']").click( function() {
        $('input[name=selection]').attr('checked', false);
        return false;
    });

    // Invert selection
    $("A[href='#invert_selection']").click( function() {
        $('input[name=selection]').each( function() {
            $(this).attr('checked', !$(this).attr('checked'));
        });
        return false;
    });

//    update_action_links();

});

function onPageChange() {
    $('[class^=emptyName]').each( function(index){
                var pid = $(this).closest('tr').attr('id').substring(3); // e.g pid323
                var data = { 'requestType': "getNames", 'personId': pid.toString()};
                var errorCallback = onGetNamesError(pid);
                $.ajax({
                    dataType: 'json',
                    type: 'POST',
                    url: '/author/claim/search_box_ajax',
                    data: {jsondata: JSON.stringify(data)},
                    success: onGetNamesSuccess,
                    error: errorCallback,
                    async: true
                });
        });

    $('[class^=emptyIDs]').each( function(index){
                var pid = $(this).closest('tr').attr('id').substring(3); // e.g pid323
                var data = { 'requestType': "getIDs", 'personId': pid.toString()};
                var errorCallback = onGetIDsError(pid);
                $.ajax({
                    dataType: 'json',
                    type: 'POST',
                    url: '/author/claim/search_box_ajax',
                    data: {jsondata: JSON.stringify(data)},
                    success: onGetIDsSuccess,
                    error: errorCallback,
                    async: true
                });
    });
    $('[class^=uncheckedProfile]').each( function(index){
                var pid = $(this).closest('tr').attr('id').substring(3); // e.g pid323
                var data = { 'requestType': "isProfileClaimed", 'personId': pid.toString()};
                var errorCallback = onIsProfileClaimedError(pid);
                $.ajax({
                    dataType: 'json',
                    type: 'POST',
                    url: '/author/claim/search_box_ajax',
                    data: {jsondata: JSON.stringify(data)},
                    success: onIsProfileClaimedSuccess,
                    error: errorCallback,
                    async: true
                });
    });
}

function onAddToMergeClick(event, button) {
    var profile = button.attr('name').toString();
    if (jQuery.inArray(profile, gMergeList) !== -1){
        return false;
    }
    var data = { 'requestType': "addProfile", 'profile': profile};
            // var errorCallback = onIsProfileClaimedError(pid);
    $.ajax({
        dataType: 'json',
        type: 'POST',
        url: '/author/claim/merge_profiles_ajax',
        data: {jsondata: JSON.stringify(data)},
        success: addToMergeList,
        // error: errorCallback,
        async: true
    });
    event.preventDefault();
}

function addToMergeList(json) {
    if(json['resultCode'] == 1) {
        var profile = json['addedPofile'];
        if ( jQuery.inArray(profile, gMergeList) == -1 && gMergeProfile !== profile) {
            gMergeList.push(profile);
            createProfilesHtml(profile);
            $('.addToMergeButton[name="' + profile + '"]').prop('disabled','disabled');
        }
    }
}

function removeFromMergeList(json) {
    if(json['resultCode'] == 1) {
        var profile = json['removedProfile'];
        var ind = jQuery.inArray(profile, gMergeList);
        if( ind !== -1) {
            gMergeList.splice(ind,1);
        }
        removeProfilesHtml(profile);
        $('.addToMergeButton[name="' + profile + '"]').removeAttr('disabled');
    }
}

function setAsPrimary(json) {
    if(json['resultCode'] == 1) {
        var profile = json['primaryProfile'];
        removeFromMergeList({'resultCode' : 1, 'removedProfile' : profile});
        var primary = gMergeProfile;
        gMergeProfile = profile;
        $('.addToMergeButton[name="' + profile + '"]').prop('disabled','disabled');
        addToMergeList({'resultCode' : 1, 'addedPofile' : primary});
        $('#primaryProfile').parent().replaceWith('<li><a id=\"primaryProfile\" href=\"' + profile +
         '\" target=\"_blank\">' + profile + '</a> <strong>(primary profile)</strong></li>');
    }
}

function createProfilesHtml(profile) {
    var $profileHtml = $('<li><a href=\"' + profile + '\" target=\"_blank\" class=\"profile\">' + profile + '</a>' +
         '<a class=\"setPrimaryProfile\" href=\"\" >Set as primary</a> <a class=\"removeProfile\" href=\"\" >Remove</a></li>');
        $('#mergeList').append($profileHtml);
        $profileHtml.find('.setPrimaryProfile').on('click', { pProfile: profile}, function(event){
            console.log('bind primary profile: ' + event.data.pProfile);
            var data = { 'requestType': "setPrimaryProfile", 'profile': event.data.pProfile};
            // var errorCallback = onIsProfileClaimedError(pid);
            $.ajax({
                dataType: 'json',
                type: 'POST',
                url: '/author/claim/merge_profiles_ajax',
                data: {jsondata: JSON.stringify(data)},
                success: setAsPrimary,
                // error: errorCallback,
                async: true
            });
            event.preventDefault();
        });
        $profileHtml.find('.removeProfile').on('click', { pProfile: profile}, function(event){
            var data = { 'requestType': "removeProfile", 'profile': event.data.pProfile};
            // var errorCallback = onIsProfileClaimedError(pid);
            $.ajax({
                dataType: 'json',
                type: 'POST',
                url: '/author/claim/merge_profiles_ajax',
                data: {jsondata: JSON.stringify(data)},
                success: removeFromMergeList,
                // error: errorCallback,
                async: true
            });
            event.preventDefault();
        });
}

function removeProfilesHtml(profile) {
    $('#mergeList').find('a[href="' + profile + '"][id!="primaryProfile"]').parent().remove();
}

function onGetIDsSuccess(json){
    if(json['resultCode'] == 1) {
        $('.emptyIDs' + json['pid']).html(json['result']).addClass('retreivedIDs').removeClass('emptyIDs' + json['pid']);

    }
    else {
        $('.emptyIDs' + json['pid']).text(json['result']);
    }
}

function onGetIDsError(pid){
  /*
   * Handle failed 'getIDs' requests.
   */
   return function (XHR, textStatus, errorThrown) {
      var pID = pid;
      $('.emptyIDs' + pID).text('External ids could not be retrieved');
    };
}

function onGetNamesSuccess(json){
    if(json['resultCode'] == 1) {
        $('.emptyName' + json['pid']).html(json['result']).addClass('retreivedName').removeClass('emptyName' + json['pid']);
    }
    else {
        $('.emptyName' + json['pid']).text(json['result']);
    }
}

function onGetNamesError(pid){
  /*
   * Handle failed 'getNames' requests.
   */
   return function (XHR, textStatus, errorThrown) {
      var pID = pid;
      $('.emptyName' + pID).text('Names could not be retrieved');
    };
}

function onIsProfileClaimedSuccess(json){
    if(json['resultCode'] == 1) {
        $('.uncheckedProfile' + json['pid']).html('<span style="color:red;">Profile already claimed</span><br/>' +
            '<span>If you think that this is actually your profile bla bla bla</span>')
        .addClass('checkedProfile').removeClass('uncheckedProfile' + json['pid']);
    }
    else {
        $('.uncheckedProfile' + json['pid']).addClass('checkedProfile').removeClass('uncheckedProfile' + json['pid']);
    }
}

function onIsProfileClaimedError(pid){
  /*
   * Handle failed 'getNames' requests.
   */
   return function (XHR, textStatus, errorThrown) {
      var pID = pid;
      $('.uncheckedProfile' + pID).text('Temporary not available');
    };
}

function onRetrievePapersSuccess(json){
    if(json['resultCode'] == 1) {
        $('.more-mpid' + json['pid']).html(json['result']).addClass('retreived_papers');
        $('.mpid' + json['pid']).append('(' + json['totalPapers'] + ')');
    }
    else {
        $('.more-mpid' + json['pid']).text(json['result']);
    }
}

function onRetrievePapersError(pid){
  /*
   * Handle failed 'getPapers' requests.
   */
   return function (XHR, textStatus, errorThrown) {
      var pID = pid;
      $('.more-mpid' + pID).text('Papers could not be retrieved');
    };
}

function onRetrieveAutoClaimedPapersSuccess(json) {
    if(json['resultCode'] == 1) {
        $('#autoclaim').replaceWith(json['result']);
    }
    else {
        $('#autoclaim').replaceWith(json['result']);
    }
}

function onRetrieveAutoClaimedPapersError(pid) {
    return function (XHR, textStatus, errorThrown) {
      var pID = pid;
      $('#autoclaim').replaceWith('<span>Error occured while retrieving papers</span>');
    };
}

function showPage(pageNum) {
    $(".aid_result:visible").hide();
    var results = $(".aid_result");
    var resultsNum = results.length;
    var start = (pageNum-1) * gResultsPerPage;
    results.slice( start, start+gResultsPerPage).show();
    var pagesNum = Math.floor(resultsNum/gResultsPerPage) + 1;
    $(".paginationInfo").text("Page " + pageNum + " of " + pagesNum);
    generateNextPage(pageNum, pagesNum);
    generatePreviousPage(pageNum, pagesNum);
}

function generateNextPage(pageNum, pagesNum) {
    if (pageNum < pagesNum ) {
        $(".nextPage").attr("disabled", false);
        $(".nextPage").off("click");
        $(".nextPage").on("click", function(event) {
            gCurPage = pageNum+1;
            showPage(gCurPage);
        });
    }
    else {
        $(".nextPage").attr("disabled", true);
    }
}

function generatePreviousPage(pageNum, pagesNum) {
    if (pageNum > 1 ) {
        $(".previousPage").attr("disabled", false);
        $(".previousPage").off("click");
        $(".previousPage").on("click", function(event) {
            gCurPage = pageNum-1;
            showPage(gCurPage);
        });
    }
    else {
        $(".previousPage").attr("disabled", true);
    }
}

function toggle_claimed_rows() {
    $('img[alt^="Confirmed."]').parents("tr").toggle()

    if ($("#toggle_claimed_rows").attr("alt") == 'hide') {
        $("#toggle_claimed_rows").attr("alt", 'show');
        $("#toggle_claimed_rows").html("Show successful claims");
    } else {
        $("#toggle_claimed_rows").attr("alt", 'hide');
        $("#toggle_claimed_rows").html("Hide successful claims");
    }
}


function confirm_bibref(claimid) {
// Performs the action of confirming a paper through an AJAX request
    var cid = claimid.replace(/\,/g, "\\," )
    var cid = cid.replace(/\:/g, "\\:")
    $('#bibref'+cid).html('<p><img src="../img/loading" style="background: none repeat scroll 0% 0% transparent;"/></p>');
    $('#bibref'+cid).load('/author/claim/status', { 'pid': $('span[id^=pid]').attr('id').substring(3),
                                                'bibref': claimid,
                                                'action': 'confirm_status' } );
//    update_action_links();
}


function repeal_bibref(claimid) {
// Performs the action of repealing a paper through an AJAX request
    var cid = claimid.replace(/\,/g, "\\," )
    var cid = cid.replace(/\:/g, "\\:")
    $('#bibref'+cid).html('<p><img src="../img/loading" style="background: none repeat scroll 0% 0% transparent;"/></p>');
    $('#bibref'+cid).load('/author/claim/status', { 'pid': $('span[id^=pid]').attr('id').substring(3),
                                                'bibref': claimid,
                                                'action': 'repeal_status' } );
//    update_action_links();
}


function reset_bibref(claimid) {
    var cid = claimid.replace(/\,/g, "\\," )
    var cid = cid.replace(/\:/g, "\\:")
    $('#bibref'+cid).html('<p><img src="../img/loading.gif" style="background: none repeat scroll 0% 0% transparent;"/></p>');
    $('#bibref'+cid).load('/author/claim/status', { 'pid': $('span[id^=pid]').attr('id').substring(3),
                                                'bibref': claimid,
                                                'action': 'reset_status' } );
//    update_action_links();
}


function action_request(claimid, action) {
// Performs the action of reseting the choice on a paper through an AJAX request
    $.ajax({
        url: "/author/claim/status",
        dataType: 'json',
        data: { 'pid': $('span[id^=pid]').attr('id').substring(3), 'action': 'json_editable', 'bibref': claimid },
        success: function(result){
            if (result.editable.length > 0) {
                if (result.editable[0] == "not_authorized") {
                    $( "<p title=\"Not Authorized\">Sorry, you are not authorized to perform this action, since this record has been assigned to another user already. Please contact the support to receive assistance</p>" ).dialog({
                        modal: true,
                        buttons: {
                            Ok: function() {
                                $( this ).dialog( "close" );
//                                update_action_links();
                            }
                        }
                    });
                } else if (result.editable[0] == "touched") {
                    $( "<p title=\"Transaction Review\">This record has been touched before (possibly by yourself). Perform action and overwrite previous decision?</p>" ).dialog({
                        resizable: true,
                        height:250,
                        modal: true,
                        buttons: {
                            "Perform Action!": function() {
                                if (action == "confirm") {
                                    confirm_bibref(claimid);
                                } else if (action == "repeal") {
                                    repeal_bibref(claimid);
                                } else if (action == "reset") {
                                    reset_bibref(claimid);
                                }

                                $( this ).dialog( "close" );
//                                update_action_links();
                            },
                            Cancel: function() {
                                $( this ).dialog( "close" );
//                                update_action_links();
                            }
                        }
                    });

                } else if (result.editable[0] == "OK") {
                    if (action == "confirm") {
                        confirm_bibref(claimid);
                    } else if (action == "repeal") {
                        repeal_bibref(claimid);
                    } else if (action == "reset") {
                        reset_bibref(claimid);
                    }
//                    update_action_links();
                } else {
//                    update_action_links();
                }

            } else {
                return false;
            }
        }
    });
}


function processJson(data) {
// Callback function of the comment's AJAX request
// 'data' is the json object returned from the server

    if (data.comments.length > 0) {
        if ($("#comments").text() == "No comments yet.") {
            $("#comments").html('<p><strong>Comments:</strong></p>\n');
        }

        $.each(data.comments, function(i, msg) {
            var values = msg.split(";;;")
            $("#comments").append('<p><em>' + values[0] + '</em><br />' + values[1] + '</p>\n');
        })
    } else {
        $("#comments").html('No comments yet.');
    }

    $('#message').val("");
}


//function update_action_links() {
//    // Alter claim links in the DOM (ensures following the non-destructive JS paradigm)
//    $('div[id^=bibref]').each(function() {
//        var claimid = $(this).attr('id').substring(6);
//        var cid = claimid.replace(/\,/g, "\\," );
//        var cid = cid.replace(/\:/g, "\\:");
//        $("#bibref"+ cid +" > #aid_status_details > #aid_confirm").attr("href", "javascript:action_request('"+ claimid +"', 'confirm')");
//        $("#bibref"+ cid +" > #aid_status_details > #aid_reset").attr("href", "javascript:action_request('"+ claimid +"', 'reset')");
//        $("#bibref"+ cid +" > #aid_status_details > #aid_repeal").attr("href", "javascript:action_request('"+ claimid +"', 'repeal')");
//   });
//}
