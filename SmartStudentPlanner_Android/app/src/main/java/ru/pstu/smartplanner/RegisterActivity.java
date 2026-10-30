package ru.pstu.smartplanner;

import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class RegisterActivity extends AppCompatActivity {

    private EditText etUsername, etEmail, etPassword;
    private TextView tvStatus;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_register);

        etUsername = findViewById(R.id.etUsername);
        etEmail = findViewById(R.id.etEmail);
        etPassword = findViewById(R.id.etPassword);
        tvStatus = findViewById(R.id.tvStatus);
        Button btnRegister = findViewById(R.id.btnRegister);
        Button btnGoToLogin = findViewById(R.id.btnGoToLogin);

        btnRegister.setOnClickListener(v -> {
            String username = etUsername.getText().toString().trim();
            String email = etEmail.getText().toString().trim();
            String password = etPassword.getText().toString().trim();

            if (username.isEmpty() || email.isEmpty() || password.isEmpty()) {
                tvStatus.setText("Заполните все поля");
                return;
            }

            tvStatus.setText("Регистрация...");
            RegisterRequest request = new RegisterRequest(username, email, password);

            ApiClient.getApi().register(request).enqueue(new Callback<UserResponse>() {
                @Override
                public void onResponse(Call<UserResponse> call, Response<UserResponse> response) {
                    if (response.isSuccessful()) {
                        tvStatus.setText("Успешно! Теперь войдите.");
                    } else {
                        tvStatus.setText("Ошибка: " + response.code());
                    }
                }

                @Override
                public void onFailure(Call<UserResponse> call, Throwable t) {
                    tvStatus.setText("Сеть недоступна: " + t.getMessage());
                }
            });
        });
        btnGoToLogin.setOnClickListener(v -> {
            finish();
        });
    }
}