from app.database import get_supabase


def insert_transaction(
    admin: dict,
    student_id: str,
    transaction_type: str,
    amount: int,
    balance_after: int,
    description: str,
) -> None:

    response = (
        get_supabase()
        .table("transactions")
        .insert(
            {
                "student_id": student_id,
                "booth_id": admin.get("booth_id"),
                "admin_id": admin["id"],
                "type": transaction_type,
                "amount": amount,
                "balance_after": balance_after,
                "description": description,
            }
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "거래 내역이 저장되지 않았습니다."
        )


def get_booth_sales(
    booth_id: str,
):
    response = (
        get_supabase()
        .table("transactions")
        .select(
            "id, amount, balance_after, "
            "description, created_at"
        )
        .eq("booth_id", booth_id)
        .eq("type", "SPEND")
        .order(
            "created_at",
            desc=True,
        )
        .limit(100)
        .execute()
    )

    transactions = response.data or []

    total_sales = sum(
        int(transaction.get("amount") or 0)
        for transaction in transactions
    )

    return {
        "total_sales": total_sales,
        "transaction_count": len(transactions),
        "transactions": transactions,
    }


def load_admin_overview():
    supabase = get_supabase()

    students_response = (
        supabase
        .table("students")
        .select(
            "id, balance, status"
        )
        .execute()
    )

    students = students_response.data or []

    total_balance = sum(
        int(student.get("balance") or 0)
        for student in students
    )

    booths_response = (
        supabase
        .table("booths")
        .select(
            "id, name, status"
        )
        .order("name")
        .execute()
    )

    booths = booths_response.data or []

    booth_names = {
        booth["id"]: (
            booth.get("name") or "부스"
        )
        for booth in booths
    }

    admins_response = (
        supabase
        .table("admins")
        .select(
            "id, username, role, booth_id, status"
        )
        .order("username")
        .execute()
    )

    admins = []

    for admin in admins_response.data or []:
        admins.append(
            {
                **admin,
                "booth_name": booth_names.get(
                    admin.get("booth_id")
                ),
            }
        )

    transactions_response = (
        supabase
        .table("transactions")
        .select(
            "id, type, amount, balance_after, "
            "description, created_at, booth_id, "
            "admin_id, student_id"
        )
        .order(
            "created_at",
            desc=True,
        )
        .limit(100)
        .execute()
    )

    recent_transactions = (
        transactions_response.data or []
    )

    amount_rows = (
        supabase
        .table("transactions")
        .select("type, amount")
        .execute()
    ).data or []

    total_charge = sum(
        int(row.get("amount") or 0)
        for row in amount_rows
        if str(
            row.get("type", "")
        ).upper() == "CHARGE"
    )

    total_spend = sum(
        int(row.get("amount") or 0)
        for row in amount_rows
        if str(
            row.get("type", "")
        ).upper() == "SPEND"
    )

    student_ids = {
        transaction["student_id"]
        for transaction in recent_transactions
        if transaction.get("student_id")
    }

    student_names = {}

    if student_ids:
        students_detail = (
            supabase
            .table("students")
            .select(
                "id, name, student_number"
            )
            .in_(
                "id",
                list(student_ids),
            )
            .execute()
        ).data or []

        for student in students_detail:
            student_names[
                student["id"]
            ] = (
                f"{student.get('name') or '-'} "
                f"({student.get('student_number') or '-'})"
            )

    admin_names = {
        admin["id"]: (
            admin.get("username") or "-"
        )
        for admin in admins
    }

    enriched_transactions = []

    for transaction in recent_transactions:
        enriched_transactions.append(
            {
                **transaction,
                "booth_name": booth_names.get(
                    transaction.get("booth_id")
                ),
                "admin_name": admin_names.get(
                    transaction.get("admin_id")
                ),
                "student_label": student_names.get(
                    transaction.get("student_id")
                ),
            }
        )

    return {
        "stats": {
            "student_count": len(students),
            "active_student_count": sum(
                1
                for student in students
                if str(
                    student.get("status", "")
                ).upper() == "ACTIVE"
            ),
            "total_balance": total_balance,
            "total_charge": total_charge,
            "total_spend": total_spend,
            "booth_count": len(booths),
            "admin_count": len(admins),
            "transaction_count": len(amount_rows),
        },
        "booths": booths,
        "admins": admins,
        "transactions": enriched_transactions,
    }