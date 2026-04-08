// Copyright (c) 2026, jignasha and contributors
// For license information, please see license.txt

frappe.query_reports["PF ECR Challan Excel"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.month_start(),
            on_change: function() {
                let from_date = frappe.query_report.get_filter_value("from_date");
                console.log("Selected from_date:", from_date);
                
                if (from_date) {
                    // Parse YYYY-MM-DD directly without time
                    let [year, month, day] = from_date.split('-').map(Number);
                    let month_end = new Date(year, month, 0);  // Day=0 = last day of previous month
                    let formatted = month_end.getFullYear() + '-' + 
                                String(month_end.getMonth() + 1).padStart(2, '0') + '-' + 
                                String(month_end.getDate()).padStart(2, '0');
                    
                    console.log("Month end calculated:", formatted);
                    frappe.query_report.set_filter_value("to_date", formatted);
                }
            }
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.month_end(),
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 0
        },
        {
            fieldname:"custom_pf_establishment_number",
            label:__("PF Establishment Number"),
            fieldtype : "Link",
            options :"PF Establishment Number"
        },
        {
            fieldname: "work_location",
            label: __("Work Location"),
            fieldtype: "Link",
            options: "Address",
            reqd: 0
        },
        {
            fieldname: "salary_slip_status",
            label: __("Salary Slip Status"),
            fieldtype: "Select",
            options: [
                "",
                "Draft",
                "Submitted"
            ],
            default: ""
        }
    ],
    onload: function(report) {
        const roles = frappe.user_roles || [];
        // Button 1: Notify Accountify Team
        if (roles.includes("S - HR Director (Global Admin)")) {
            report.page.add_inner_button("Notify Accountify Team", () => {
                frappe.call({
                    method: "prompt_hr.py.accounting_team_notifications.send_esic_challan_notification",
                    args: {
                        report_name: "PF ECR Challan Excel",
                        url: window.location.href,
                    },
                    callback: function(r) {
                        if (r.message === "success") {
                            frappe.msgprint("Notification sent to Accounting team Succesfully.");
                        }
                    }
                });
            }).removeClass("btn-default").addClass("btn-primary");
        }
    
        report.page.add_inner_button('Download Text File', async function() {
            // 1. Fetch the report data
            const result = await frappe.call({
                method: "frappe.desk.query_report.run",
                args: {
                    report_name: "PF ECR Challan Excel",
                    filters: report.get_filter_values()
                }
            });
            // 2. Process the data
            const data = result.message.result;
            const columns = result.message.columns.map(col => col.label);
            // 3. Format as text with #~# separator
            let lines = [];
            data.forEach(row => {
                const rowText = Object.values(row).map(val => {
                    // If value is null, undefined, or empty string
                    if (val === null || val === undefined || val === '') {
                        // If the value is expected to be a number, put 0, else null
                        // Try to detect number type
                        return typeof val === 'number' || (!isNaN(val) && val !== '') ? 0 : 'Null';
                    }
                    // If value is a number, return as is
                    if (typeof val === 'number') return val;
                    // For other types, return as is
                    return val;
                }).join("#~#");
                lines.push(rowText);
            });
            const textContent = lines.join("\n");
            // 4. Trigger download
            const blob = new Blob([textContent], {type: "text/plain"});
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "pf_ecr_challan_report.txt";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        }, 'Actions');
    },
};
