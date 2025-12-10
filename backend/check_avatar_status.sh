#!/bin/bash
# Quick avatar troubleshooting commands

echo "=========================================="
echo "AVATAR STORAGE QUICK CHECKS"
echo "=========================================="
echo ""

echo "1. Check which users have avatars:"
echo "----------------------------------------"
mysql -u root -proot hello_db -e "
SELECT userid, email, first_name,
       CASE WHEN avatar IS NULL THEN '❌ No avatar' 
            ELSE CONCAT('✅ Has avatar (', ROUND(LENGTH(avatar)/1024), ' KB)') 
       END as avatar_status
FROM users
ORDER BY updated_at DESC
LIMIT 10;
"

echo ""
echo "2. Check specific user (enter user ID):"
echo "----------------------------------------"
read -p "Enter user ID (or press Enter to skip): " USER_ID

if [ ! -z "$USER_ID" ]; then
    mysql -u root -proot hello_db -e "
    SELECT userid, email, first_name, last_name,
           CASE WHEN avatar IS NULL THEN '❌ No avatar' 
                ELSE CONCAT('✅ Has avatar (', ROUND(LENGTH(avatar)/1024), ' KB)') 
           END as avatar_status,
           created_at, updated_at
    FROM users
    WHERE userid = '$USER_ID';
    "
fi

echo ""
echo "3. Avatar statistics:"
echo "----------------------------------------"
mysql -u root -proot hello_db -e "
SELECT 
    COUNT(*) as total_users,
    SUM(CASE WHEN avatar IS NOT NULL THEN 1 ELSE 0 END) as users_with_avatar,
    SUM(CASE WHEN avatar IS NULL THEN 1 ELSE 0 END) as users_without_avatar,
    ROUND(AVG(LENGTH(avatar))/1024, 2) as avg_avatar_size_kb,
    ROUND(MAX(LENGTH(avatar))/1024, 2) as max_avatar_size_kb,
    ROUND(MIN(LENGTH(avatar))/1024, 2) as min_avatar_size_kb
FROM users;
"

echo ""
echo "4. Recent avatar updates:"
echo "----------------------------------------"
mysql -u root -proot hello_db -e "
SELECT userid, email, first_name,
       ROUND(LENGTH(avatar)/1024) as size_kb,
       updated_at
FROM users
WHERE avatar IS NOT NULL
ORDER BY updated_at DESC
LIMIT 5;
"

echo ""
echo "5. Check Flask logs for avatar activity:"
echo "----------------------------------------"
echo "Looking for recent SAVE-AVATAR or UPDATE-AVATAR logs..."
echo ""

if [ -f "flask_server.log" ]; then
    echo "From flask_server.log:"
    tail -50 flask_server.log | grep -E "SAVE-AVATAR|UPDATE-AVATAR" | tail -20
elif command -v journalctl &> /dev/null; then
    echo "From systemd journal:"
    sudo journalctl -u bcf-backend --no-pager -n 100 | grep -E "SAVE-AVATAR|UPDATE-AVATAR" | tail -20
else
    echo "⚠️ No logs found. Flask server might not be running or logs not configured."
fi

echo ""
echo "=========================================="
echo "TROUBLESHOOTING COMPLETED"
echo "=========================================="
