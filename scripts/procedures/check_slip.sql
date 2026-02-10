CREATE OR REPLACE FUNCTION public.check_slip(p_pos_id bigint)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_cam_count smallint;
  v_f1 text;
  v_f2 text;
  v_is_outside boolean;

  v_req1 int[];
  v_req2 int[];

  v_order_th int[];

  v_is_f1_valid boolean := false;
  v_is_f2_valid boolean := false;
  v_slip_ok boolean := false;

  v_bad_idx_f1 int[];
  v_bad_idx_f2 int[];

  v_msg text;

  -- новые “детализации” вида: "3: 4 < 6"
  v_bad_pairs_f1 text[];
  v_bad_pairs_f2 text[];
BEGIN
  SELECT cam_count, f1, f2, coalesce(is_oytside, false)
  INTO v_cam_count, v_f1, v_f2, v_is_outside
  FROM public.qual_analize_pos
  WHERE id = p_pos_id;

  -- cam_count=0 (одно стекло) — НЕ ошибка, проверку слипания пропускаем
  IF COALESCE(v_cam_count, 0) = 0 THEN
    DELETE FROM public.qual_analize_pos_issues
    WHERE pos_id = p_pos_id
      AND issue_code IN ('SLIP_FORMULA_MISSING','SLIP_MISMATCH');
    RETURN;
  END IF;

  -- ===== Если обе формулы отсутствуют =====
  IF v_f1 IS NULL AND v_f2 IS NULL THEN
    DELETE FROM public.qual_analize_pos_issues
    WHERE pos_id = p_pos_id
      AND issue_code = 'SLIP_FORMULA_MISSING';

    INSERT INTO public.qual_analize_pos_issues(pos_id, issue_code, severity, message, context)
    VALUES (
      p_pos_id,
      'SLIP_FORMULA_MISSING',
      'error',
      'Отсутствует формула в таблице слипания (не найдены f1 и f2)',
      jsonb_build_object('cam_count', v_cam_count)
    );

    DELETE FROM public.qual_analize_pos_issues
    WHERE pos_id = p_pos_id
      AND issue_code = 'SLIP_MISMATCH';

    RETURN;
  ELSE
    DELETE FROM public.qual_analize_pos_issues
    WHERE pos_id = p_pos_id
      AND issue_code = 'SLIP_FORMULA_MISSING';
  END IF;

  -- Требования из БД (min толщины по элементам)
  v_req1 := public.parse_slip_formula(v_f1);
  v_req2 := public.parse_slip_formula(v_f2);

  -- Фактическая структура заказа (толщины по всем элементам: стекла+рамки)
  SELECT array_agg(e.thickness ORDER BY e.ord)
  INTO v_order_th
  FROM public.parse_order_elements_full(
    (SELECT position_formula FROM public.qual_analize_pos WHERE id = p_pos_id)
  ) e;

  -- ПЕРЕВАРАЧИВАЕМ, если открывание наружу
  IF v_is_outside THEN
    SELECT array_agg(elem ORDER BY nr DESC)
    INTO v_order_th
    FROM unnest(v_order_th) WITH ORDINALITY AS t(elem, nr);
  END IF;

  IF v_order_th IS NULL OR array_length(v_order_th, 1) IS NULL THEN
    RETURN;
  END IF;

  -- ===== F1: проверка длины + толщин =====
  v_bad_idx_f1 := NULL;
  v_bad_pairs_f1 := NULL;

  IF v_req1 IS NOT NULL AND array_length(v_req1, 1) = array_length(v_order_th, 1) THEN
    SELECT array_agg(i ORDER BY i)
    INTO v_bad_idx_f1
    FROM generate_subscripts(v_order_th, 1) g(i)
    WHERE v_order_th[i] < v_req1[i];

    v_is_f1_valid := (v_bad_idx_f1 IS NULL);

    -- детали "i: факт < требование"
    IF v_bad_idx_f1 IS NOT NULL THEN
      SELECT array_agg(format('%s: %s < %s', i, v_order_th[i], v_req1[i]) ORDER BY i)
      INTO v_bad_pairs_f1
      FROM unnest(v_bad_idx_f1) u(i);
    END IF;
  ELSE
    v_is_f1_valid := false;
  END IF;

  -- ===== F2: проверка длины + толщин =====
  v_bad_idx_f2 := NULL;
  v_bad_pairs_f2 := NULL;

  IF v_req2 IS NOT NULL AND array_length(v_req2, 1) = array_length(v_order_th, 1) THEN
    SELECT array_agg(i ORDER BY i)
    INTO v_bad_idx_f2
    FROM generate_subscripts(v_order_th, 1) g(i)
    WHERE v_order_th[i] < v_req2[i];

    v_is_f2_valid := (v_bad_idx_f2 IS NULL);

    -- детали "i: факт < требование"
    IF v_bad_idx_f2 IS NOT NULL THEN
      SELECT array_agg(format('%s: %s < %s', i, v_order_th[i], v_req2[i]) ORDER BY i)
      INTO v_bad_pairs_f2
      FROM unnest(v_bad_idx_f2) u(i);
    END IF;
  ELSE
    v_is_f2_valid := false;
  END IF;

  v_slip_ok := (v_is_f1_valid OR v_is_f2_valid);

  -- ===== Если всё ок — чистим старую ошибку (если была) =====
  IF v_slip_ok THEN
    DELETE FROM public.qual_analize_pos_issues
    WHERE pos_id = p_pos_id
      AND issue_code = 'SLIP_MISMATCH';
    RETURN;
  END IF;

  -- ===== Формируем человекочитаемое сообщение =====
  v_msg := 'Несоответствие структуры стеклопакета таблице слипания.';

  v_msg := v_msg || format(
    E'\nФактическая структура (толщины по порядку): %s',
    array_to_string(v_order_th, '-')
  );

  IF v_req1 IS NOT NULL THEN
    v_msg := v_msg || format(
      E'\nОжидание по f1: %s (min: %s)',
      coalesce(v_f1, '—'),
      array_to_string(v_req1, '-')
    );

    IF v_bad_idx_f1 IS NOT NULL THEN
      v_msg := v_msg || format(
        E'\nНе проходит по f1 (индексы): %s',
        array_to_string(v_bad_idx_f1, ', ')
      );

      v_msg := v_msg || format(
        E'\nДетали по f1 (индекс: факт < min): %s',
        array_to_string(v_bad_pairs_f1, '; ')
      );
    END IF;
  END IF;

  IF v_req2 IS NOT NULL THEN
    v_msg := v_msg || format(
      E'\nОжидание по f2: %s (min: %s)',
      coalesce(v_f2, '—'),
      array_to_string(v_req2, '-')
    );

    IF v_bad_idx_f2 IS NOT NULL THEN
      v_msg := v_msg || format(
        E'\nНе проходит по f2 (индексы): %s',
        array_to_string(v_bad_idx_f2, ', ')
      );

      v_msg := v_msg || format(
        E'\nДетали по f2 (индекс: факт < min): %s',
        array_to_string(v_bad_pairs_f2, '; ')
      );
    END IF;
  END IF;

  -- антидубли (перезапись)
  DELETE FROM public.qual_analize_pos_issues
  WHERE pos_id = p_pos_id
    AND issue_code = 'SLIP_MISMATCH';

  INSERT INTO public.qual_analize_pos_issues(pos_id, issue_code, severity, message, context)
  VALUES (
    p_pos_id,
    'SLIP_MISMATCH',
    'error',
    v_msg,
    jsonb_build_object(
      'cam_count', v_cam_count,
      'order_thickness', v_order_th,
      'f1', v_f1,
      'f2', v_f2,
      'f1_req', v_req1,
      'f2_req', v_req2,
      'f1_bad_indexes', v_bad_idx_f1,
      'f2_bad_indexes', v_bad_idx_f2,
      'f1_bad_pairs', v_bad_pairs_f1,
      'f2_bad_pairs', v_bad_pairs_f2,
      'f1_valid', v_is_f1_valid,
      'f2_valid', v_is_f2_valid
    )
  );

END;
$function$;