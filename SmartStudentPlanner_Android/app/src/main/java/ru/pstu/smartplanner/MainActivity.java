package ru.pstu.smartplanner;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class MainActivity extends AppCompatActivity {

    private EditText etIdentifier, etPassword;
    private TextView tvStatus;
    private Button btnLogin, btnGoToRegister;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login); // Привязка к экрану входа

        etIdentifier = findViewById(R.id.etIdentifier);
        etPassword = findViewById(R.id.etPassword);
        tvStatus = findViewById(R.id.tvStatus);
        btnLogin = findViewById(R.id.btnLogin);
        btnGoToRegister = findViewById(R.id.btnGoToRegister);

        btnLogin.setOnClickListener(v -> {
            String identifier = etIdentifier.getText().toString().trim();
            String password = etPassword.getText().toString().trim();

            if (identifier.isEmpty() || password.isEmpty()) {
                tvStatus.setText("Заполните все поля");
                return;
            }

            tvStatus.setText("Вход...");
            LoginRequest request = new LoginRequest(identifier, password);

            ApiClient.getApi().login(request).enqueue(new Callback<TokenResponse>() {
                @Override
                public void onResponse(Call<TokenResponse> call, Response<TokenResponse> response) {
                    if (response.isSuccessful() && response.body() != null) {
                        tvStatus.setText("Успешный вход! Токен получен.");
                        // Здесь потом можно сохранить токен в SharedPreferences
                    } else {
                        tvStatus.setText("Ошибка входа: " + response.code());
                    }
                }

                @Override
                public void onFailure(Call<TokenResponse> call, Throwable t) {
                    tvStatus.setText("Сеть недоступна: " + t.getMessage());
                }
            });
        });

        btnGoToRegister.setOnClickListener(v -> {
            Intent intent = new Intent(MainActivity.this, RegisterActivity.class);
            startActivity(intent);
        });
    }
}