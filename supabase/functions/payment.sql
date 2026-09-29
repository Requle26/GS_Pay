create or replace function public.process_payment(
    p_student_id uuid,
    p_booth_id uuid,
    p_admin_id uuid,
    p_menu_id uuid
)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare
    v_student students%rowtype;
    v_menu menus%rowtype;
    v_balance_after integer;
begin
    select *
    into v_menu
    from public.menus
    where id = p_menu_id
      and booth_id = p_booth_id
      and status = 'ACTIVE'
    for update;

    if not found then
        raise exception '판매 중인 메뉴가 아닙니다.';
    end if;

    select *
    into v_student
    from public.students
    where id = p_student_id
      and status = 'ACTIVE'
    for update;

    if not found then
        raise exception '사용할 수 없는 학생증입니다.';
    end if;

    if v_student.balance < v_menu.price then
        raise exception '잔액이 부족합니다.';
    end if;

    v_balance_after :=
        v_student.balance - v_menu.price;

    update public.students
    set balance = v_balance_after
    where id = v_student.id
      and status = 'ACTIVE';

    insert into public.transactions (
        student_id,
        booth_id,
        admin_id,
        type,
        amount,
        balance_after,
        description
    )
    values (
        v_student.id,
        p_booth_id,
        p_admin_id,
        'SPEND',
        v_menu.price,
        v_balance_after,
        v_menu.name || ' 결제'
    );

    return json_build_object(
        'menu',
        row_to_json(v_menu),
        'student',
        json_build_object(
            'id', v_student.id,
            'name', v_student.name,
            'balance', v_balance_after,
            'status', v_student.status
        )
    );
end;
$$;