import os
import re
import traceback
from pytube import YouTube
import validators
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv('TOKEN')
MAX_FILE_SIZE_MB = 50

progress_messages = {}
cancel_flags = {}

def validar_url_youtube(url):
    if not validators.url(url):
        return False
    yt_regex = r"^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+$"
    return re.match(yt_regex, url) is not None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 Bienvenido al YouTube Downloader Bot!\n"
        "📥 Envía un enlace de YouTube válido.\n"
        "Usa /cancelar para detener descargas."
    )

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cancel_flags[chat_id] = True
    await update.message.reply_text("❌ Descarga cancelada.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    chat_id = update.effective_chat.id

    if text == "cancelar":
        cancel_flags[chat_id] = True
        await update.message.reply_text("❌ Descarga cancelada.")
        return

    if validar_url_youtube(text):
        await update.message.reply_text("📥 ¿Quieres descargarlo como 'video' o 'audio'?")
        context.user_data['url'] = text
        cancel_flags[chat_id] = False

    elif text in ['video', 'audio']:
        if 'url' not in context.user_data:
            await update.message.reply_text("Primero envíame un enlace de YouTube válido.")
            return

        context.user_data['tipo'] = text
        if text == 'video':
            await enviar_resoluciones(update, context)
        else:
            await descargar_y_enviar(update, context, context.user_data['url'], 'audio')

    elif 'resoluciones' in context.user_data:
        if text in context.user_data['resoluciones']:
            context.user_data['resolucion_elegida'] = text
            await descargar_y_enviar(update, context, context.user_data['url'], 'video')
        else:
            await update.message.reply_text("❌ Resolución no válida. Elige una disponible.")
    else:
        await update.message.reply_text("❌ Enlace inválido o comando desconocido.")

async def enviar_resoluciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        yt = YouTube(context.user_data['url'])
        streams = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc()
        resoluciones = sorted(set([s.resolution for s in streams if s.resolution]), reverse=True)
        context.user_data['resoluciones'] = [r.lower() for r in resoluciones]

        if not resoluciones:
            await update.message.reply_text("⚠️ No hay resoluciones disponibles para este video.")
            return

        await update.message.reply_text("📺 Resoluciones disponibles:\n" + "\n".join(resoluciones))
        await update.message.reply_text("📌 Responde con la resolución que deseas (ej: 720p, 480p).")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error al obtener resoluciones.")
        print("Error resoluciones:", traceback.format_exc())

def on_progress(stream, chunk, bytes_remaining):
    percent = int(100 * (1 - bytes_remaining / stream.filesize))
    chat_id = stream._context['chat_id']
    message = progress_messages.get(chat_id)
    app = stream._context['app']

    if cancel_flags.get(chat_id):
        raise Exception("Descarga cancelada por el usuario.")

    if percent % 5 == 0:
        if message:
            app.create_task(message.edit_text(f"📥 Descargando... {percent}%"))

async def descargar_y_enviar(update: Update, context: ContextTypes.DEFAULT_TYPE, url, tipo):
    chat_id = update.effective_chat.id
    file_path = None
    try:
        yt = YouTube(url, on_progress_callback=on_progress)
        yt.register_on_progress_callback(on_progress)
        yt._context = {'chat_id': chat_id, 'app': context.application}

        msg = await update.message.reply_text("⏳ Preparando descarga...")
        yt._context['message_id'] = msg.message_id
        progress_messages[chat_id] = msg

        if tipo == "video":
            res = context.user_data.get('resolucion_elegida')
            stream = yt.streams.filter(progressive=True, file_extension='mp4', resolution=res).first()
            if not stream:
                await update.message.reply_text("❌ Resolución no disponible.")
                return
        else:
            stream = yt.streams.filter(only_audio=True).first()

        if not stream:
            await update.message.reply_text("❌ No se encontró el stream adecuado.")
            return

        file_size_mb = stream.filesize / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            await update.message.reply_text(f"⚠️ El archivo pesa {file_size_mb:.2f} MB y excede el límite.")
            return

        safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', yt.title)
        file_path = stream.download(output_path="descargas", filename=safe_title)

        if tipo == "audio":
            base, ext = os.path.splitext(file_path)
            file_path_mp3 = base + '.mp3'
            os.rename(file_path, file_path_mp3)
            file_path = file_path_mp3

        with open(file_path, 'rb') as f:
            await update.message.reply_document(document=InputFile(f))

        await update.message.reply_text("✅ Descarga completada.")

    except Exception as e:
        if str(e) == "Descarga cancelada por el usuario.":
            await update.message.reply_text("❌ Descarga cancelada.")
        else:
            await update.message.reply_text(f"⚠️ Error durante la descarga.")
            print("Error descarga:", traceback.format_exc())

    finally:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        progress_messages.pop(chat_id, None)
        context.user_data.clear()

def main():
    if not os.path.exists("descargas"):
        os.makedirs("descargas")

    if not TOKEN:
        print("ERROR: No se encontró la variable de entorno TOKEN")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancelar", cancelar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot corriendo seguro...")
    app.run_polling()

if __name__ == "__main__":
    main()
