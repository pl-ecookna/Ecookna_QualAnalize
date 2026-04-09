CREATE OR REPLACE FUNCTION public.trg_calc_qual_pos()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_width_round   int;
  v_height_round  int;
  v_cam_count     smallint;
  v_sc            record;
BEGIN
  -- Защита от NULL размеров
  IF NEW.position_width IS NULL OR NEW.position_hight IS NULL THEN
    NEW.position_width_round := NULL;
    NEW.position_hight_round := NULL;
    NEW.cam_count := NULL;
    NEW.f1 := NULL;
    NEW.f2 := NULL;
    NEW.position_formula_slip := NULL;
    RETURN NEW;
  END IF;

  -- 1) Округление размеров (<=50 вниз, >=51 вверх)
  v_width_round :=
    (NEW.position_width / 100) * 100
    + CASE WHEN (NEW.position_width % 100) >= 51 THEN 100 ELSE 0 END;

  v_height_round :=
    (NEW.position_hight / 100) * 100
    + CASE WHEN (NEW.position_hight % 100) >= 51 THEN 100 ELSE 0 END;

  NEW.position_width_round := v_width_round;
  NEW.position_hight_round := v_height_round;

  -- 2) Количество камер: считаем элементы-рамки после разбиения формулы
  SELECT count(*)::smallint
  INTO v_cam_count
  FROM public.parse_order_elements(coalesce(NEW.position_formula, ''))
  WHERE element_type = 'frame';

  NEW.cam_count := v_cam_count;

  -- 3) Поиск строки в size_control (по округленным размерам, без учёта ориентации)
  SELECT s.*
  INTO v_sc
  FROM public.size_control s
  WHERE LEAST(s.dim1, s.dim2) = LEAST(v_width_round, v_height_round)
    AND GREATEST(s.dim1, s.dim2) = GREATEST(v_width_round, v_height_round)
  LIMIT 1;

  -- 4) Заполнение f1 / f2 / marking
  IF FOUND THEN
    NEW.position_formula_slip := v_sc.marking;

    CASE v_cam_count
      WHEN 1 THEN
        NEW.f1 := v_sc.formula_1_1k;
        NEW.f2 := v_sc.formula_2_1k;
      WHEN 2 THEN
        NEW.f1 := v_sc.formula_1_2k;
        NEW.f2 := v_sc.formula_2_2k;
      WHEN 3 THEN
        NEW.f1 := v_sc.formula_1_3k;
        NEW.f2 := v_sc.formula_2_3k;
      ELSE
        -- cam_count = 0 или >3 — формул нет
        NEW.f1 := NULL;
        NEW.f2 := NULL;
    END CASE;
  ELSE
    NEW.f1 := NULL;
    NEW.f2 := NULL;
    NEW.position_formula_slip := NULL;
  END IF;

  RETURN NEW;
END;
$function$;
