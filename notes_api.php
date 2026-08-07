<?php
/**
 * EkranHisse Notes API
 * NOT: Bu dosya aktif olarak kullanılmıyor. Notlar GitHub Gist API üzerinden
 * yönetilmektedir (notes_api_client.py). Bu dosya alternatif bir self-hosted
 * backend olarak referans amaçlı bırakılmıştır.
 *
 * GET  → tüm notları döndür
 * POST {"action":"save","notes":[...]} → kaydet
 *
 * Güvenlik: EKRANHISSE_SECRET ortam değişkeninden okunan token ile korunuyor.
 * notes_data.json dosyasını web root dışına taşıyabilirsin.
 */

define('SECRET', getenv('EKRANHISSE_SECRET') ?: 'ekranhisse_secret_2024');
define('DATA_FILE', __DIR__ . '/notes_data.json');

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-Secret');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// Token kontrolü — yalnızca X-Secret header'ı kabul edilir (GET query param log'lara düşer)
$token = $_SERVER['HTTP_X_SECRET'] ?? '';
if ($token !== SECRET) {
    http_response_code(403);
    echo json_encode(['error' => 'Forbidden']);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    if (!file_exists(DATA_FILE)) {
        echo json_encode(['notes' => []]);
        exit;
    }
    $data = file_get_contents(DATA_FILE);
    echo $data ?: json_encode(['notes' => []]);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $body = file_get_contents('php://input');
    $payload = json_decode($body, true);

    if (!isset($payload['action']) || $payload['action'] !== 'save') {
        http_response_code(400);
        echo json_encode(['error' => 'bad request']);
        exit;
    }

    $notes = $payload['notes'] ?? [];
    $out = json_encode(['notes' => $notes], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
    file_put_contents(DATA_FILE, $out, LOCK_EX);
    echo json_encode(['ok' => true]);
    exit;
}

http_response_code(405);
echo json_encode(['error' => 'method not allowed']);
