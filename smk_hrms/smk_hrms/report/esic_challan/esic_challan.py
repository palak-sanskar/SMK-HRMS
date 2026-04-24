# Copyright (c) 2026, jignasha and contributors
# For license information, please see license.txt


import frappe
from frappe.utils import getdate, add_months, format_date


def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"fieldname": "ip_number",
			"label": "IP Number",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "ip_name",
			"label": "IP Name",
			"fieldtype": "Data",
			"width": 300
		},
		{
			"fieldname": "total_no_of_days",
			"label": "No of days for which wages paid/payable during the month",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "total_monthly_wages",
			"label": "Total Monthly Wages",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"fieldname": "reason",
			"label": "Reason Code for Zero Working Days",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname":"last_working_day",
			"label": "Last Working Day",
			"fieldtype": "Date",
			"width": 150
		}
	]

# ? CONSIDER ADDING FIELDS LIKE GROSS PAY, DEDUCTIONS, NET PAY IN REPORT FOR BETTER CLARITY. ALSO ADD REASON CODES FOR ZERO WORKING DAYS
def get_data(filters):
    # * SET FROM AND TO DATE FROM FILTERS
    from_date = getdate(filters.get("from_date")) or getdate()
    to_date = getdate(filters.get("to_date")) or add_months(from_date, 1)

    # * BASE SALARY SLIP FILTERS
    salary_filters = {
        "start_date": from_date,
        "end_date": to_date,
    }

    # * Add docstatus filter based on salary_slip_status filter
    salary_slip_status = filters.get("salary_slip_status")
    if salary_slip_status:
        if salary_slip_status == "Draft":
            salary_filters["docstatus"] = 0
        elif salary_slip_status == "Submitted":
            salary_filters["docstatus"] = 1

    if filters.get("company"):
        salary_filters["company"] = filters.get("company")

    # * FETCH SALARY SLIPS
    slip_datas = frappe.get_all(
        "Salary Slip",
        filters=salary_filters,
        fields=["*"],
        order_by="creation desc"
    )

    data = []

    # * LOOP THROUGH SALARY SLIPS
    for slip_data in slip_datas:
        employee = frappe.get_doc("Employee", slip_data.employee)
        if employee.custom_esic != 1:
            continue

        if filters.get("work_location"):
            if employee.custom_work_location != filters.get("work_location"):
                continue
        if filters.get("custom_esi_establishment_number"):
            if employee.custom_esi_establishment_number != filters.get("custom_esi_establishment_number"):
                continue
        
        # * Determine salary slip status
        slip_status = "Draft" if slip_data.docstatus == 0 else "Submitted"
        
        relieving_date = getdate(employee.relieving_date) if employee.relieving_date else None

        # * DEFAULT REASON CODE
        reason_code = ""
        last_working_day = ""

        if slip_data.payment_days == 0:
            #? REASON 1 - ZERO WORKING DAYS
            reason_code = "1"
            slip_data.gross_pay = 0
            slip_data.payment_days = 0

        elif relieving_date and from_date <= relieving_date <= to_date:
            #? REASON 2 - RELIEVED THIS MONTH
            reason_code = "2"
            last_working_day = relieving_date

        # * FILTER BY SALARY STRUCTURE ASSIGNMENT AND BASE CONDITION
        # if slip_data.custom_salary_structure_assignment:
        #     salary_structure_assignment = frappe.get_doc(
        #         "Salary Structure Assignment",
        #         slip_data.custom_salary_structure_assignment
        #     )
        salary_structure_assignment = None

        # * Always fetch from Salary Structure
        if slip_data.salary_structure:
            salary_structure_assignment_data = frappe.get_all(
                "Salary Structure Assignment",
                filters={
                    "employee": slip_data.employee,
                    "salary_structure": slip_data.salary_structure
                },
                fields=["name", "base"],
                order_by="from_date desc",
                limit=1
            )

            if salary_structure_assignment_data:
                salary_structure_assignment = salary_structure_assignment_data[0]

            # * SHOW IN REPORT ONLY IF EMPLOYEE BASE SALARY <= 21000
            # if salary_structure_assignment.base <= 21000:
            if salary_structure_assignment.base:

                # * INITIAL GROSS PAY
                gross_pay = slip_data.gross_pay
                salary_details  = frappe.get_all(
                    "Salary Detail",
                    filters={
                        "parent": slip_data.name,
                        "parentfield": "earnings",
                    },
                    fields=["salary_component", "amount"]
                )
                for salary_detail in salary_details:
                    salary_component = frappe.get_doc("Salary Component", salary_detail.salary_component)
                    # * CONSIDER BASIC COMPONENT ONLY FOR GROSS PAY CALCULATION
                    if salary_component.custom_salary_component_type == "Basic":
                        gross_pay = salary_detail.amount
			
                row = {
                    "ip_number": employee.custom_esi_number,
                    # "employee": employee.name,
                    "ip_name": slip_data.employee_name,
                    # "custom_esi_establishment_number":employee.custom_esi_establishment_number,
                    # "work_location": employee.custom_work_location,
                    # "salary_slip_status": slip_status,
                    "total_no_of_days": slip_data.payment_days,
                    "total_monthly_wages": gross_pay,
                    "reason": reason_code,
                    "last_working_day": last_working_day
                }

                data.append(row)

    return data
