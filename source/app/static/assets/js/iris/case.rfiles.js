/* reload the rfiles table */
function reload_rfiles() {
    get_case_rfiles();
    notify_success("Refreshed");
}


Table = $("#rfiles_table").DataTable({
    dom: 'Blfrtip',
    aaData: [],
    aoColumns: [
      {
        "data": "filename",
        "render": function (data, type, row, meta) {
          if (type === 'display') {
            if (isWhiteSpace(data)) {
                data = '#' + row['id'];
            }
            data = '<a  data-toggle="tooltip" href="#" title="' + data + '" onclick="edit_rfiles(\'' + row['id'] + '\');">' + data +'</a>';
          }
          return data;
        }
      },
      { "data": "date_added" },
      { "data": "file_hash" },
      { "data": "file_size" },
      { "data": "file_description" },
      { "data": "username" }
    ],
    filter: true,
    info: true,
    ordering: true,
    processing: true,
    retrieve: true,
    buttons: [
    ]
});
$("#rfiles_table").css("font-size", 12);
var buttons = new $.fn.dataTable.Buttons(Table, {
     buttons: [
        { "extend": 'csvHtml5', "text":'<i class="fas fa-cloud-download-alt"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Download as CSV' },
        { "extend": 'copyHtml5', "text":'<i class="fas fa-copy"></i>',"className": 'btn btn-link text-white'
        , "titleAttr": 'Copy' },
    ]
}).container().appendTo($('#tables_button'));

/* Retrieve the list of rfiles and build a datatable for each type of rfiles */
function get_case_rfiles() {
    $.ajax({
        url: "/case/evidences/list" + case_param(),
        type: "GET",
        dataType: 'json',
        success: function (response) {
            if (response.status == 'success') {
                if (response.data != null) {
                    jsdata = response.data;
                    Table.clear();
                    Table.rows.add(jsdata.evidences);
                    Table.columns.adjust().draw();

                    set_last_state(jsdata.state);
                    hide_loader();

                    $('#rfiles_table_wrapper').show();

                } else {
                    Table.clear().draw();
                    swal("Oh no !", data.message, "error")
                }
            } else {
                Table.clear().draw()
            }
        },
        error: function (error) {
            swal("Oh no !", error.statusText, "error")
        }
    });
}

/* Edit an rfiles */
function edit_rfiles(rfiles_id) {
    url = 'evidences/' + rfiles_id + '/modal' + case_param();
    $('#modal_add_rfiles_content').load(url, function () {});
    $('#modal_add_rfiles').modal({ show: true });
}

/* Update an rfiles */
function update_rfile(rfiles_id) {
    var data_sent = $('form#form_edit_rfile').serializeObject();
    data_sent['csrf_token'] = $('#csrf_token').val();

    $.ajax({
        url: 'evidences/update/' + rfiles_id + case_param(),
        type: "POST",
        data: JSON.stringify(data_sent),
        contentType: "application/json;charset=UTF-8",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                swal("You're set !",
                    "The file has been updated on register successfully",
                    {
                        icon: "success",
                        timer: 500
                    }
                ).then((value) => {
                    reload_rfiles();
                    $('#modal_add_rfiles').modal('hide');
                });

            } else {
                $('#submit_new_rfiles').text('Save again');
                swal("Oh no !", data.message, "error")
            }
        },
        error: function (error) {
            notify_error(error.responseJSON.message);
            propagate_form_api_errors(error.responseJSON.data);
        }
    });
}

/* Delete an rfiles */
function delete_rfile(rfiles_id) {
    $.ajax({
        url: 'evidences/delete/' + rfiles_id + case_param(),
        type: "GET",
        dataType: "json",
        success: function (data) {
            if (data.status == 'success') {
                swal("Good !",
                    "The file has been deleted from register successfully",
                    {
                        icon: "success",
                        timer: 500
                    }
                ).then((value) => {
                    reload_rfiles();
                    $('#modal_add_rfiles').modal('hide');
                });

            } else {
                swal("Oh no !", data.message, "error")
            }
        },
        error: function (error) {
            swal("Oh no !", error.statusText, "error")
            }
    });
}

/* Modal to add rfiles is closed, clear its contents */
$('.modal').on('hidden.bs.modal', function () {
    $(this).find('form').trigger('reset');
    $('#btn_rfile_proc').text('Process');
})

/* Page is ready, fetch the rfiles of the case */
$(document).ready(function(){
    get_case_rfiles();
    setInterval(function() { check_update('evidences/state'); }, 3000);

});
