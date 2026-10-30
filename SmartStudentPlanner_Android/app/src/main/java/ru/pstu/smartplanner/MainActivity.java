package ru.pstu.smartplanner;

import android.os.Bundle;
import android.widget.Button;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class MainActivity extends AppCompatActivity {

    private TextView tvResult;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        tvResult = findViewById(R.id.tvResult);
        Button btnTest = findViewById(R.id.btnTest);

        btnTest.setOnClickListener(v -> {
            tvResult.setText("Отправка запроса...");

            RegisterRequest reg = new RegisterRequest(
                    "olga_test_" + System.currentTimeMillis() % 10000,
                    "olga" + System.currentTimeMillis() % 10000 + "@test.com",
                    "password123"
            );

            ApiClient.getApi().register(reg).enqueue(new Callback<UserResponse>() {
                @Override
                public void onResponse(Call<UserResponse> call, Response<UserResponse> response) {
                    if (response.isSuccessful()) {
                        tvResult.setText("Регистрация OK: " + response.body().username);
                    } else {
                        tvResult.setText("Ошибка регистрации: " + response.code());
                    }
                }

                @Override
                public void onFailure(Call<UserResponse> call, Throwable t) {
                    tvResult.setText("Сеть недоступна: " + t.getMessage());
                }
            });
        });
    }
}