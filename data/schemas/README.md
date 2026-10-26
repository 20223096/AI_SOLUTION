# ETL 출력 스키마

대용량 CSV는 Git에 포함하지 않고 `python scripts/noise_etl.py`로 재생성합니다.

`sdot_sinchon_clean.csv`: sensor_id, sensor_serial, observed_at(Asia/Seoul ISO 8601), district, neighborhood, noise_avg/max/min, record_type, collected_at, quality_status, quality_reasons, duplicate_status, source_file, source_sha256, provenance(JSON).

`road_noise_sinchon_clean.csv`: measurement_date, hour_ending(원본 1~24 표기), station_name, noise_level, metric, source_period, source_file/member, quality_status, provenance(JSON).

`background_profile.csv`: profile_id, day_type, hour(0~23; 도로자료 hour_ending 24는 0으로 표현), representative_db(중앙값), mean_db, observation_count, metric, calculation_eligible.

서로 다른 metric은 같은 프로파일로 합산하지 않습니다. `quality_status=held`는 삭제가 아니라 집계 보류입니다.
