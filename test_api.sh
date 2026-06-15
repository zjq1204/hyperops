#!/bin/bash
set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
FAILED=0

echo "=== HyperOps API 单元测试 ==="
echo ""

# 1. 健康检查
echo "[1/8] 测试健康检查..."
RESP=$(curl -s "$BASE_URL/health")
if echo "$RESP" | grep -q "OK"; then
    echo "  ✓ 健康检查通过"
else
    echo "  ✗ 健康检查失败: $RESP"
    FAILED=1
fi

# 2. 登录
echo "[2/8] 测试登录..."
RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"admin123"}')
TOKEN=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('access','') or d.get('access',''))" 2>/dev/null)
if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
    echo "  ✓ 登录成功"
else
    echo "  ✗ 登录失败: $RESP"
    FAILED=1
fi

# 3. 获取用户信息
echo "[3/8] 测试获取用户信息..."
if [ -n "$TOKEN" ]; then
    RESP=$(curl -s "$BASE_URL/api/v1/auth/user" -H "Authorization: Bearer $TOKEN")
    if echo "$RESP" | grep -q "username"; then
        echo "  ✓ 获取用户信息成功"
        echo "  用户: $(echo $RESP | python3 -c 'import sys,json; print(json.load(sys.stdin).get("data",{}).get("username","") or json.load(sys.stdin).get("username",""))' 2>/dev/null)"
    else
        echo "  ✗ 获取用户信息失败: $RESP"
        FAILED=1
    fi
else
    echo "  - 跳过 (无token)"
fi

# 4. Jenkins - 获取实例列表
echo "[4/8] 测试Jenkins实例列表..."
if [ -n "$TOKEN" ]; then
    RESP=$(curl -s "$BASE_URL/api/v1/jenkins/instances/" -H "Authorization: Bearer $TOKEN")
    if echo "$RESP" | grep -q "results\|data"; then
        echo "  ✓ Jenkins实例列表API正常"
    else
        echo "  ✗ Jenkins实例列表失败: $RESP"
        FAILED=1
    fi
else
    echo "  - 跳过 (无token)"
fi

# 5. Jenkins - 获取触发入口
echo "[5/8] 测试Jenkins触发入口..."
if [ -n "$TOKEN" ]; then
    RESP=$(curl -s "$BASE_URL/api/v1/jenkins/user/entries/" -H "Authorization: Bearer $TOKEN")
    if echo "$RESP" | grep -q "results\|data\|count"; then
        echo "  ✓ Jenkins触发入口API正常"
    else
        echo "  ✗ Jenkins触发入口失败: $RESP"
        FAILED=1
    fi
else
    echo "  - 跳过 (无token)"
fi

# 6. GitLab - 获取实例列表
echo "[6/8] 测试GitLab实例列表..."
if [ -n "$TOKEN" ]; then
    RESP=$(curl -s "$BASE_URL/api/v1/gitlab/instances/" -H "Authorization: Bearer $TOKEN")
    if echo "$RESP" | grep -q "results\|data"; then
        echo "  ✓ GitLab实例列表API正常"
    else
        echo "  ✗ GitLab实例列表失败: $RESP"
        FAILED=1
    fi
else
    echo "  - 跳过 (无token)"
fi

# 7. GitLab - 获取群组列表
echo "[7/8] 测试GitLab群组列表..."
if [ -n "$TOKEN" ]; then
    RESP=$(curl -s "$BASE_URL/api/v1/gitlab/groups/" -H "Authorization: Bearer $TOKEN")
    if echo "$RESP" | grep -q "results\|data"; then
        echo "  ✓ GitLab群组列表API正常"
    else
        echo "  ✗ GitLab群组列表失败: $RESP"
        FAILED=1
    fi
else
    echo "  - 跳过 (无token)"
fi

# 8. 测试404
echo "[8/8] 测试404处理..."
RESP=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/nonexistent/")
if [ "$RESP" = "404" ]; then
    echo "  ✓ 404处理正确"
else
    echo "  ✗ 404处理异常: HTTP $RESP"
    FAILED=1
fi

echo ""
echo "=== 测试完成 ==="
if [ $FAILED -eq 0 ]; then
    echo "全部通过 ✓"
    exit 0
else
    echo "有失败 ✗"
    exit 1
fi
