// Copyright (c) 2026, jignasha and contributors
// For license information, please see license.txt

frappe.query_reports["ESIC Challan"] = {
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
                    
                    frappe.query_report.set_filter_value("to_date", formatted);
                }
            }
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.month_end()
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 0
        },
        {
            fieldname: "work_location",
            label: __("Work Location"),
            fieldtype: "Link",
            options: "Address",
            reqd: 0
        },
        {
            fieldname: "custom_esi_establishment_number",
            label: __("ESI Establishment Number"),
            fieldtype: "Link",
            options: "ESI Establishment Number",
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
};
