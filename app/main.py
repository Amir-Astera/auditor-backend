# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.responses import JSONResponse
# from modules.rag.gemini import GeminiAPI, logger

# app = FastAPI(
#     title="Gemini File Analyzer",
#     description="API для анализа PDF, DOCX и TXT файлов с помощью Google Gemini File API"
# )

# gemini_api = GeminiAPI()

# @app.post("/analyze-file/", summary="Анализ загруженного файла")
# async def analyze_file_route(
#     file: UploadFile = File(..., description="Файл для анализа (PDF, DOCX, TXT)"),
#     prompt: str = "Суммируй этот документ и выдели ключевые выводы."
# ):
#     file_info = None
#     try:
#         file_data = await file.read()
#         # 1️⃣ Загрузка файла
#         file_info = gemini_api.upload_file(file_data=file_data, file_name=file.filename, mime_type=file.content_type)
#         file_name = file_info["name"]

#         # 2️⃣ Генерация текста с файлом
#         response_json = gemini_api.generate_content_with_file(file_name=file_name, prompt=prompt)

#         result_text = response_json["candidates"][0]["content"]["parts"][0]["text"]
#         return JSONResponse({"analysis_result": result_text})

#     except Exception as e:
#         logger.error(f"Ошибка в роутере анализа файла: {e}")
#         raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

#     finally:
#         if file_info:
#             logger.info(f"Файл {file_info['name']} будет автоматически удалён по истечении expirationTime.")
