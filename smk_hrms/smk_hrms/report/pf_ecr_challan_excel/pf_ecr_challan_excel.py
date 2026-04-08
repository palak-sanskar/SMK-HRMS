# Copyright (c) 2025, Jignasha Chavda and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, add_months
import calendar

def execute(filters=None):
    # Set the month and year from filters or default to current month
    from_date = filters.get("from_date") or getdate()
    to_date = filters.get("to_date") or add_months(from_date, 1)
    
    columns = [
        {"label": "UAN", "fieldname": "employee_number", "fieldtype": "Data", "width": 120},
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "width": 180, "options":"Employee"},
        {"label": "MEMBER NAME", "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
        {"label":"Name as per Aadhar","fieldname":"custom_name_as_per_aadhaar","fieldtype":"Data","width":180},
        {"label":"PF Establishment Number","fieldname":"custom_pf_establishment_number","fieldtype":"Link","options":"PF Establishment Number","width":180},
        {"label": "Work Location", "fieldname": "work_location", "fieldtype": "Link", "width": 180, "options":"Address"},
        {"label": "Salary Slip Status", "fieldname": "salary_slip_status", "fieldtype": "Data", "width": 150},
        {"label": "GROSS WAGES", "fieldname": "gross_wages", "fieldtype": "Currency", "width": 200},
        {"label": "EPF WAGES", "fieldname": "epf_wages", "fieldtype": "Currency", "width": 200},
        {"label": "EPS WAGES", "fieldname": "eps_wages", "fieldtype": "Currency", "width": 200},
        {"label": "EDLI WAGES", "fieldname": "edli_wages", "fieldtype": "Currency", "width": 200},
        {"label": "EPF CONTRI REMITTED", "fieldname": "ee_share_remitted", "fieldtype": "Currency", "width": 200},
        {"label": "EPS CONTRI REMITTED", "fieldname": "eps_contribution_remitted", "fieldtype": "Currency", "width": 200},
        {"label": "EPF EPS DIFF REMITTED", "fieldname": "er_share_remitted", "fieldtype": "Currency", "width": 200},
        {"label": "NCP DAYS", "fieldname": "ncp_days", "fieldtype": "Int", "width": 120},
        {"label": "REFUNDS", "fieldname": "refund_of_advance", "fieldtype": "Data", "editable":1, "width": 150},
    ]

    data = []
    
    # Base filters
    salary_filters = {
        "start_date": from_date,
        "end_date": to_date,
    }
    
    # Add docstatus filter based on salary_slip_status filter
    salary_slip_status = filters.get("salary_slip_status")
    if salary_slip_status:
        if salary_slip_status == "Draft":
            salary_filters["docstatus"] = 0
        elif salary_slip_status == "Submitted":
            salary_filters["docstatus"] = 1
    else:
        # If no status selected, get both draft and submitted
        pass  # We'll handle this differently
    
    # Add company filter only if present
    if filters.get("company"):
        salary_filters["company"] = filters.get("company")
    
    # Fetch salary slips based on filters
    if salary_slip_status:
        # Specific status selected
        salary_slips = frappe.get_all(
            "Salary Slip",
            fields=["employee", "employee_name", "gross_pay", "name", "leave_without_pay", "docstatus"],
            filters=salary_filters
        )
    else:
        # No status filter - get all (draft and submitted)
        salary_filters_all = salary_filters.copy()
        salary_filters_all.pop("docstatus", None)  # Remove docstatus filter if exists
        salary_slips = frappe.get_all(
            "Salary Slip",
            fields=["employee", "employee_name", "gross_pay", "name", "leave_without_pay", "docstatus"],
            filters=salary_filters_all
        )

    for slip in salary_slips:
        employee = frappe.get_doc("Employee", slip.employee)
        custom_pf_establishment_number = employee.custom_pf_establishment_number
        
        if not employee.custom_pf_consent:
            continue
        
        if filters.get("work_location"):
            if employee.custom_work_location != filters.get("work_location"):
                continue
        
        if filters.get("custom_pf_establishment_number"):
            if employee.custom_pf_establishment_number != filters.get("custom_pf_establishment_number"):
                continue
        
        # Determine salary slip status
        slip_status = "Draft" if slip.docstatus == 0 else "Submitted"
        
        salary_details = frappe.get_all(
            "Salary Detail",
            filters={"parent": slip.name},
            fields=["salary_component", "amount", "parentfield"],
        )
        print("salary_details", salary_details)


        basic = 0
        provident_fund = 0
        ee_share_remitted = 0
        if salary_details:
            for salary_detail in salary_details:
                salary_comp = frappe.get_doc("Salary Component", salary_detail.salary_component)
                if salary_comp.custom_salary_component_type == "Basic" or salary_comp.custom_salary_component_type == "Dearness Allowance":
                    basic += salary_detail.amount
                elif salary_comp.custom_salary_component_type == "PF Employer" and salary_detail.parentfield=="deductions":
                    provident_fund += salary_detail.amount

                # ? If EE share is already specified in Salary Detail, use that instead of calculating from wages
                print("salary_comp", salary_comp.name, salary_comp.custom_salary_component_type)
                if salary_comp.custom_salary_component_type == "PF" and salary_detail.parentfield=="deductions":
                    ee_share_remitted = salary_detail.amount

        print("provident_fund", provident_fund)

        epf_wages = basic
       
        if epf_wages > 15000:
            eps_wages = 15000
        else:   
            eps_wages = epf_wages
        
        #  In 'EPF WAGES' column, add condition to limit at 15000 (same as condition set in EPS WAGES column)
        if epf_wages > 15000:
            epf_wages = 15000
        
        if employee.custom_eps_consent == 0:
            eps_wages = 0
            eps_contribution_remitted = 0

        if ee_share_remitted == 0:
            ee_share_remitted = epf_wages * 0.12
        eps_contribution_remitted = eps_wages * 0.0833

        if ee_share_remitted > 1800:
            er_share_remitted = 1800 - round(eps_contribution_remitted)
        elif ee_share_remitted <= 1800:
            er_share_remitted = round(ee_share_remitted) - round(eps_contribution_remitted)

        
        if provident_fund > 0:
            row = {
                "employee_number": employee.custom_uan_number,
                "employee": employee.name,
                "employee_name": slip.employee_name,
                "custom_name_as_per_aadhaar":employee.custom_name_as_per_aadhaar,
                "custom_pf_establishment_number":custom_pf_establishment_number,
                "work_location": employee.custom_work_location,
                "salary_slip_status": slip_status,
                "gross_wages": round(slip.gross_pay),
                "epf_wages": round(epf_wages),
                "eps_wages": round(epf_wages) if employee.custom_eps_consent else 0,
                "edli_wages": round(epf_wages),
                "ee_share_remitted": round(ee_share_remitted),
                "eps_contribution_remitted": round(eps_contribution_remitted) if employee.custom_eps_consent else 0,
                "er_share_remitted": round(er_share_remitted),
                "ncp_days": round(float(slip.leave_without_pay)),
                "refund_of_advance": 0,
            }
            data.append(row)
    print("data", data)
    return columns, data
