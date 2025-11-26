const stdoutText = $input.first().json.stdout;

let parsedData;
try {
  parsedData = JSON.parse(stdoutText);
} catch (error) {
  // JSON 형식이 아닐 경우 에러 처리 (빈 배열 반환 등)
  console.log("JSON 파싱 에러:", error);
  return [];
}

return parsedData.map(item => {
  return {
    json: {
      event: item.event,
      state: item.state,
      FilePath: item.FilePath
    }
  };
});